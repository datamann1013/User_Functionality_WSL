use actix_multipart::Multipart;
use actix_web::{get, post, web, App, HttpResponse, HttpServer, Responder, Result, HttpRequest};
use chrono::{Duration, Utc};
use qrcode::QrCode;
use qrcode::render::svg;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use if_addrs::get_if_addrs;
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

fn base_url_from_req(req: &HttpRequest) -> String {
    if let Ok(ext) = std::env::var("RUNECORE_EXTERNAL_URL") {
        let trimmed = ext.trim_end_matches('/').to_string();
        if trimmed.starts_with("http://") || trimmed.starts_with("https://") {
            return trimmed;
        } else {
            return format!("http://{}", trimmed);
        }
    }
    let info = req.connection_info();
    let scheme = info.scheme();
    let host = info.host();
    format!("{}://{}", scheme, host)
}

#[get("/interfaces")]
async fn get_interfaces(req: HttpRequest) -> Result<impl Responder> {
    let mut candidates: Vec<String> = Vec::new();

    let port = std::env::var("PORT").unwrap_or_else(|_| "5010".into());

    // 1) environment override — highest priority, explicit admin setting
    if let Ok(ext) = std::env::var("RUNECORE_EXTERNAL_URL") {
        let trimmed = ext.trim_end_matches('/').to_string();
        if trimmed.starts_with("http://") || trimmed.starts_with("https://") {
            candidates.push(trimmed);
        } else {
            candidates.push(format!("http://{}", trimmed));
        }
    }

    // 2) Extract request base early (connection_info borrow must not outlive the async section)
    let req_base = {
        let info = req.connection_info();
        format!("{}://{}", info.scheme(), info.host())
    };

    // 3) Query CoreMemory (via Core proxy) for the real host LAN IPs published by Sentinel.
    //    Sentinel runs on the host, so it records real IPv4 addresses (192.168.x.x, 10.x.x.x)
    //    — not the Docker bridge IPs this container would see via if_addrs.
    if let Ok(core_url) = std::env::var("RUNECORE_CORE_URL") {
        let query_url = format!(
            "{}/api/proxy/CoreMemoryAPI/v1/memories/query",
            core_url.trim_end_matches('/')
        );
        let body = serde_json::json!({"namespace": "machine_profile", "top_k": 1});
        if let Ok(client) = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(3))
            .build()
        {
            if let Ok(resp) = client.post(&query_url).json(&body).send().await {
                if let Ok(data) = resp.json::<serde_json::Value>().await {
                    if let Some(ifaces) = data
                        .get("results")
                        .and_then(|r| r.as_array())
                        .and_then(|r| r.first())
                        .and_then(|first| first.get("metadata"))
                        .and_then(|m| m.get("network_interfaces"))
                        .and_then(|n| n.as_array())
                    {
                        for iface in ifaces {
                            if let Some(ip) = iface.get("ip").and_then(|v| v.as_str()) {
                                candidates.push(format!("http://{}:{}", ip, port));
                            }
                        }
                    }
                }
            }
        }
    }

    // 4) Host from request (typically localhost:port when accessed through docker port mapping)
    candidates.push(req_base);

    // 5) Container's own non-loopback IPv4 addresses — fallback when Sentinel/CoreMemory unavailable
    if let Ok(addrs) = get_if_addrs() {
        for ifa in addrs {
            if ifa.is_loopback() { continue; }
            if let std::net::IpAddr::V4(ipv4) = ifa.ip() {
                candidates.push(format!("http://{}:{}", ipv4, port));
            }
        }
    }

    // dedupe while preserving order
    let mut seen = std::collections::HashSet::new();
    let mut out = Vec::new();
    for c in candidates {
        if seen.insert(c.clone()) { out.push(c); }
    }

    Ok(HttpResponse::Ok().json(serde_json::json!({"candidates": out})))
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
async fn upload(req: HttpRequest, mut payload: Multipart, data: web::Data<std::sync::Mutex<AppStateData>>) -> Result<impl Responder> {
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
        // web::block returns Result<Result<T, io::Error>, BlockingError> — propagate both
        web::block(move || {
            let mut f = std::fs::File::create(&write_path)?;
            f.write_all(&buf)?;
            Ok::<(), std::io::Error>(())
        }).await
            .map_err(|e| actix_web::error::ErrorInternalServerError(e))?
            .map_err(|e| actix_web::error::ErrorInternalServerError(e))?;

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

        // allow client override via query param external_base or header X-EXTERNAL-BASE
        let mut base = None;
        if let Some(q) = req.query_string().split('&').find_map(|kv| {
            let mut parts = kv.splitn(2, '=');
            let k = parts.next()?; let v = parts.next()?; if k == "external_base" { Some(v) } else { None }
        }) {
            base = Some(q.to_string());
        }
        if base.is_none() {
            if let Some(h) = req.headers().get("X-EXTERNAL-BASE") {
                if let Ok(s) = h.to_str() { base = Some(s.to_string()); }
            }
        }
        let base = match base {
            Some(b) => {
                let t = b.trim_end_matches('/').to_string();
                if t.starts_with("http://") || t.starts_with("https://") { t } else { format!("http://{}", t) }
            }
            None => base_url_from_req(&req)
        };

        let download_url = format!("{}/download/{}?token={}", base.trim_end_matches('/'), file_id, token);
        let qr_svg = match QrCode::new(download_url.as_bytes()) {
            Ok(code) => code.render::<svg::Color>().build(),
            Err(e) => return Ok(HttpResponse::InternalServerError().body(format!("QR generation failed: {}", e))),
        };

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
async fn download(_req: HttpRequest, path: web::Path<String>, query: web::Query<HashMap<String, String>>, data: web::Data<std::sync::Mutex<AppStateData>>) -> Result<actix_files::NamedFile> {
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

// Build a reqwest client that optionally trusts a provided CA file and/or allows insecure TLS.
fn build_reqwest_client(allow_insecure: bool) -> Result<reqwest::Client, reqwest::Error> {
    let mut builder = reqwest::Client::builder();
    if allow_insecure {
        builder = builder.danger_accept_invalid_certs(true);
    }
    // If the environment provides a CA path, try to add it as a root certificate.
    if let Ok(ca_path) = std::env::var("RUNECORE_CORE_CA_PATH") {
        if let Ok(pem) = std::fs::read(&ca_path) {
            if let Ok(cert) = reqwest::Certificate::from_pem(&pem) {
                builder = builder.add_root_certificate(cert);
            }
        }
    }
    builder.build()
}

#[post("/register_with_core")]
async fn register_with_core(req_body: String) -> impl Responder {
    // Expect a JSON body like {"insecure": true}
    let parsed: serde_json::Value = match serde_json::from_str(&req_body) {
        Ok(v) => v,
        Err(_) => return HttpResponse::BadRequest().json(serde_json::json!({"error":"invalid json"})),
    };

    let insecure = parsed.get("insecure").and_then(|v| v.as_bool()).unwrap_or(false);

    // Server-side guard: only allow insecure registration if env var explicitly set.
    let allow_insecure = std::env::var("RUNECORE_ALLOW_INSECURE_REGISTRATION").unwrap_or_else(|_| "false".into()) == "true";
    if insecure && !allow_insecure {
        return HttpResponse::Forbidden().json(serde_json::json!({"error":"insecure registration not allowed by server configuration"}));
    }

    let core_url = std::env::var("RUNECORE_CORE_URL").unwrap_or_else(|_| "http://localhost:5000/api/modules/register".into());
    let register_name = "RuneMesh_Drop";
    let register_body = serde_json::json!({
        "name": register_name,
        "version": "0.1.0",
        "port": std::env::var("PORT").unwrap_or_else(|_| "5010".into()),
        "rest_url": format!("http://mesh_drop:{}", std::env::var("PORT").unwrap_or_else(|_| "5010".into())),
        "capabilities": ["file_transfer", "qr_code"]
    });

    match build_reqwest_client(insecure) {
        Ok(client) => {
            match client.post(&core_url).json(&register_body).send().await {
                Ok(resp) => {
                    let status = resp.status().as_u16();
                    let text = resp.text().await.unwrap_or_else(|_| "".into());
                    return HttpResponse::Ok().json(serde_json::json!({"status": "sent", "http_status": status, "body": text}));
                }
                Err(e) => return HttpResponse::InternalServerError().json(serde_json::json!({"error": format!("request failed: {}", e.to_string())})),
            }
        }
        Err(e) => return HttpResponse::InternalServerError().json(serde_json::json!({"error": format!("client build failed: {}", e.to_string())})),
    }
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    println!("Starting RuneMesh_Drop service ...");
    ensure_dirs()?;
    let state = load_meta();

    let data = web::Data::new(std::sync::Mutex::new(state));

    // Try to register with core (best-effort)
    let core_url = std::env::var("RUNECORE_CORE_URL").unwrap_or_else(|_| "http://localhost:5000/api/modules/register".into());
    let register_name = "RuneMesh_Drop";
    let register_body = serde_json::json!({
        "name": register_name,
        "version": "0.1.0",
        "port": std::env::var("PORT").unwrap_or_else(|_| "5010".into()),
        "rest_url": format!("http://mesh_drop:{}", std::env::var("PORT").unwrap_or_else(|_| "5010".into())),
        "capabilities": ["file_transfer", "qr_code"]
    });

    // fire-and-forget registration
    let core_url_clone = core_url.clone();
    let register_body_clone = register_body.clone();
    // Respect the environment toggle for allowing insecure registration.
    // Default behaviour is strict TLS. To allow insecure (dev-only), set
    // RUNECORE_ALLOW_INSECURE_REGISTRATION=true in the container environment.
    let allow_insecure = std::env::var("RUNECORE_ALLOW_INSECURE_REGISTRATION").unwrap_or_else(|_| "false".into()) == "true";
    let core_url_spawn = core_url_clone.clone();
    let body_spawn = register_body_clone.clone();
    actix_web::rt::spawn(async move {
        if let Ok(client) = build_reqwest_client(allow_insecure) {
            let _ = client.post(&core_url_spawn).json(&body_spawn).send().await;
        }
    });

    // new endpoint to allow a runtime, user-triggered registration attempt
    // (useful for the frontend opt-in flow). This endpoint will only permit
    // insecure registration if RUNECORE_ALLOW_INSECURE_REGISTRATION is true.

    let bind = format!("0.0.0.0:{}", std::env::var("PORT").unwrap_or_else(|_| "5010".into()));
    println!("Listening on {}", bind);

    HttpServer::new(move || {
        App::new()
            .app_data(data.clone())
            // API routes registered first so they are not shadowed by the file server
            .service(upload)
            .service(download)
            .service(post_signal)
            .service(get_signal)
            .service(health)
            .service(register_with_core)
            // Static file server last — serves the Vite-built frontend for all other paths
            .service(actix_files::Files::new("/", "./frontend-dist").index_file("index.html"))
    })
    .bind(bind)?
    .run()
    .await
}
