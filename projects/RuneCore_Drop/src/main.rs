use actix_multipart::Multipart;
use actix_web::{get, post, web, App, HttpResponse, HttpServer, Responder, Result, HttpRequest};
use chrono::{Duration, Utc};
use qrcode::QrCode;
use qrcode::render::svg;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::io::Write;
use bytes::BytesMut;
use futures_util::StreamExt;
use uuid::Uuid;

#[derive(Serialize, Deserialize, Clone)]
struct FileMeta {
    file_id: String,
    filename: String,
    path: String,
    token: String,
    expires_at: chrono::DateTime<chrono::Utc>,
}

#[derive(Serialize, Deserialize, Default)]
struct AppStateData {
    // persisted map file_id -> FileMeta
    files: HashMap<String, FileMeta>,
    // in-memory signaling messages: file_id -> Vec<(seq, msg)>
    signals: HashMap<String, Vec<String>>,
}

const STORAGE_DIR: &str = "./storage/uploads";
const META_FILE: &str = "./storage/metadata.json";

fn ensure_dirs() -> std::io::Result<()> {
    fs::create_dir_all(STORAGE_DIR)?;
    Ok(())
}

fn load_meta() -> AppStateData {
    match fs::read_to_string(META_FILE) {
        Ok(s) => serde_json::from_str(&s).unwrap_or_default(),
        Err(_) => AppStateData::default(),
    }
}

fn save_meta(state: &AppStateData) {
    if let Ok(s) = serde_json::to_string_pretty(state) {
        let _ = fs::create_dir_all("./storage");
        let _ = fs::write(META_FILE, s);
    }
}

#[post("/signal/{file_id}")]
async fn post_signal(path: web::Path<String>, body: String, data: web::Data<std::sync::Mutex<AppStateData>>) -> Result<impl Responder> {
    let file_id = path.into_inner();
    let mut state = data.lock().unwrap();
    let entry = state.signals.entry(file_id).or_insert_with(Vec::new);
    entry.push(body);
    Ok(HttpResponse::Ok().json(serde_json::json!({"status":"ok","count": entry.len()})))
}

#[get("/signal/{file_id}")]
async fn get_signal(path: web::Path<String>, query: web::Query<HashMap<String, String>>, data: web::Data<std::sync::Mutex<AppStateData>>) -> Result<impl Responder> {
    let file_id = path.into_inner();
    let start_idx: usize = query.get("from").and_then(|s| s.parse().ok()).unwrap_or(0);
    let state = data.lock().unwrap();
    if let Some(vec) = state.signals.get(&file_id) {
        let slice = if start_idx < vec.len() { vec[start_idx..].to_vec() } else { vec![] };
        return Ok(HttpResponse::Ok().json(serde_json::json!({"from": start_idx, "messages": slice}))); 
    }
    Ok(HttpResponse::Ok().json(serde_json::json!({"from": start_idx, "messages": []})))
}

#[post("/upload")]
async fn upload(mut payload: Multipart, data: web::Data<std::sync::Mutex<AppStateData>>) -> Result<impl Responder> {
    ensure_dirs().map_err(|e| actix_web::error::ErrorInternalServerError(e))?;

    // Handle only first file field for MVP
    while let Some(item) = payload.next().await {
        let mut field = item.map_err(|e| actix_web::error::ErrorBadRequest(e))?;
        let content_disposition = field.content_disposition();
        let filename = content_disposition
            .get_filename()
            .map(|s| s.to_string())
            .unwrap_or_else(|| format!("file-{}", Uuid::new_v4()));

        let file_id = Uuid::new_v4().to_string();
        let filepath = format!("{}/{}", STORAGE_DIR, file_id);

        // Accumulate chunks into memory then write once (simple MVP approach)
        let mut buf = BytesMut::new();
        while let Some(chunk) = field.next().await {
            let data = chunk.map_err(|e| actix_web::error::ErrorInternalServerError(e))?;
            buf.extend_from_slice(&data);
        }

        // write to disk in a blocking task (clone path for move into closure)
        let write_path = filepath.clone();
        web::block(move || {
            let mut f = std::fs::File::create(&write_path)?;
            f.write_all(&buf)?;
            Ok::<(), std::io::Error>(())
        }).await.map_err(|e| actix_web::error::ErrorInternalServerError(e))?;

        // create token and expire
        let token = Uuid::new_v4().to_string();
        let expires_at = Utc::now() + Duration::hours(48); // default retention while QR shown

        let meta = FileMeta {
            file_id: file_id.clone(),
            filename: filename.clone(),
            path: filepath.clone(),
            token: token.clone(),
            expires_at,
        };

        {
            let mut state = data.lock().unwrap();
            state.files.insert(file_id.clone(), meta.clone());
            save_meta(&state);
        }

        let download_url = format!("/download/{}?token={}", file_id, token);
        let qr_svg = QrCode::new(&format!("{}", download_url)).unwrap().render::<svg::Color>().build();

        let resp = serde_json::json!({
            "file_id": file_id,
            "filename": filename,
            "download_url": download_url,
            "token": token,
            "qr_svg": qr_svg,
        });

        return Ok(HttpResponse::Ok().json(resp));
    }

    Ok(HttpResponse::BadRequest().body("no file uploaded"))
}

#[get("/download/{file_id}")]
async fn download(req: HttpRequest, path: web::Path<String>, query: web::Query<HashMap<String, String>>, data: web::Data<std::sync::Mutex<AppStateData>>) -> Result<actix_files::NamedFile> {
    let file_id = path.into_inner();
    let token_q = query.get("token");

    let state = data.lock().unwrap();
    if let Some(meta) = state.files.get(&file_id) {
        if let Some(token) = token_q {
            if token == &meta.token {
                if Utc::now() <= meta.expires_at {
                    let file_path = meta.path.clone();
                    let fname = meta.filename.clone();
                    let named_file = actix_files::NamedFile::open_async(file_path).await.map_err(|_| actix_web::error::ErrorNotFound("file not found"))?;
                    let cd = actix_web::http::header::ContentDisposition{
                        disposition: actix_web::http::header::DispositionType::Attachment,
                        parameters: vec![actix_web::http::header::DispositionParam::Filename(fname)],
                    };
                    return Ok(named_file.set_content_disposition(cd));
                }
                return Err(actix_web::error::ErrorForbidden("token expired"));
            }
            return Err(actix_web::error::ErrorForbidden("invalid token"));
        }
        return Err(actix_web::error::ErrorBadRequest("missing token"));
    }

    Err(actix_web::error::ErrorNotFound("file not found"))
}

#[get("/health")]
async fn health() -> impl Responder {
    HttpResponse::Ok().json(serde_json::json!({"status": "healthy"}))
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    println!("Starting RuneDrop service (RuneCore_Drop) ...");
    ensure_dirs()?;
    let state = load_meta();

    let data = web::Data::new(std::sync::Mutex::new(state));

    // Try to register with core (best-effort)
    let core_url = std::env::var("RUNECORE_CORE_URL").unwrap_or_else(|_| "http://localhost:5000/api/modules/register".into());
    let register_name = "RuneDrop";
    let register_body = serde_json::json!({"name": register_name, "version": "0.1.0", "port": std::env::var("PORT").unwrap_or_else(|_| "5010".into()), "capabilities": ["file_sharing"]});

    // fire-and-forget registration
    let core_url_clone = core_url.clone();
    let register_body_clone = register_body.clone();
    actix_web::rt::spawn(async move {
        let client = reqwest::Client::builder().danger_accept_invalid_certs(true).build();
        if let Ok(c) = client {
            let _ = c.post(&core_url_clone).json(&register_body_clone).send().await;
        }
    });

    let bind = format!("0.0.0.0:{}", std::env::var("PORT").unwrap_or_else(|_| "5010".into()));
    println!("Listening on {}", bind);

    HttpServer::new(move || {
        App::new()
            .app_data(data.clone())
            // serve the frontend static files at /frontend
            .service(actix_files::Files::new("/frontend", "./frontend").index_file("index.html"))
            .service(upload)
            .service(download)
            .service(post_signal)
            .service(get_signal)
            .service(health)
    })
    .bind(bind)?
    .run()
    .await
}
