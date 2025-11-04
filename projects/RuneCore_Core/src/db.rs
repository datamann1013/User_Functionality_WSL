use sqlx::{SqlitePool, sqlite::SqlitePoolOptions, FromRow};
use std::path::Path;
use anyhow::Result;
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug, Clone, FromRow)]
pub struct ServiceRow {
    pub id: String,
    pub name: String,
    pub version: Option<String>,
    pub ws_url: Option<String>,
    pub rest_url: Option<String>,
    pub public_key_pem: Option<String>,
}

pub async fn init_db(data_dir: &str) -> Result<SqlitePool> {
    let db_path = Path::new(data_dir).join("runecore.db");
    let db_url = format!("sqlite://{}", db_path.to_string_lossy());
    let pool = SqlitePoolOptions::new().max_connections(5).connect(&db_url).await?;

    sqlx::query(
        r#"CREATE TABLE IF NOT EXISTS services (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            version TEXT,
            ws_url TEXT,
            rest_url TEXT,
            public_key_pem TEXT
        )"#,
    )
    .execute(&pool)
    .await?;

    Ok(pool)
}

pub async fn insert_service(pool: &SqlitePool, svc: &ServiceRow) -> Result<()> {
    sqlx::query(
        r#"INSERT OR REPLACE INTO services (id,name,version,ws_url,rest_url,public_key_pem)
           VALUES (?1,?2,?3,?4,?5,?6)"#,
    )
    .bind(&svc.id)
    .bind(&svc.name)
    .bind(&svc.version)
    .bind(&svc.ws_url)
    .bind(&svc.rest_url)
    .bind(&svc.public_key_pem)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn list_services(pool: &SqlitePool) -> Result<Vec<ServiceRow>> {
    let rows = sqlx::query_as::<_, ServiceRow>(
        r#"SELECT id, name, version, ws_url, rest_url, public_key_pem FROM services"#,
    )
    .fetch_all(pool)
    .await?;
    Ok(rows)
}
