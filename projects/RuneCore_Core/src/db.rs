use sqlx::{SqlitePool, sqlite::{SqlitePoolOptions, SqliteConnectOptions}, FromRow};
use std::str::FromStr;
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
    #[serde(default)]
    pub dependencies: String, // JSON array stored as string
    #[serde(default)]
    pub wishlist: String, // JSON array stored as string
    #[serde(default)]
    pub container_name: Option<String>,
    #[serde(default)]
    pub status: String, // "running", "limb_mode", "degraded", "temporarily_offline", "permanently_offline"
    #[serde(default)]
    pub last_seen: i64, // Unix timestamp
    #[serde(default)]
    pub offline_since: Option<i64>, // Unix timestamp when marked offline
}

impl ServiceRow {
    pub fn dependencies_list(&self) -> Vec<String> {
        serde_json::from_str(&self.dependencies).unwrap_or_default()
    }

    pub fn wishlist_list(&self) -> Vec<String> {
        serde_json::from_str(&self.wishlist).unwrap_or_default()
    }
}

pub async fn init_db(data_dir: &str) -> Result<SqlitePool> {
    let db_path = Path::new(data_dir).join("runecore.db");
    let connect_opts = SqliteConnectOptions::from_str(&format!("sqlite://{}", db_path.to_string_lossy()))?
        .create_if_missing(true);
    let pool = SqlitePoolOptions::new().max_connections(5).connect_with(connect_opts).await?;

    sqlx::query(
        r#"CREATE TABLE IF NOT EXISTS services (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            version TEXT,
            ws_url TEXT,
            rest_url TEXT,
            public_key_pem TEXT,
            dependencies TEXT DEFAULT '[]',
            wishlist TEXT DEFAULT '[]',
            container_name TEXT,
            status TEXT DEFAULT 'running',
            last_seen INTEGER DEFAULT 0,
            offline_since INTEGER
        )"#,
    )
    .execute(&pool)
    .await?;

    sqlx::query("CREATE INDEX IF NOT EXISTS idx_services_name ON services(name)")
        .execute(&pool)
        .await?;

    sqlx::query("CREATE INDEX IF NOT EXISTS idx_services_status ON services(status)")
        .execute(&pool)
        .await?;

    Ok(pool)
}

pub async fn insert_service(pool: &SqlitePool, svc: &ServiceRow) -> Result<()> {
    let now = chrono::Utc::now().timestamp();
    sqlx::query(
        r#"INSERT OR REPLACE INTO services
           (id, name, version, ws_url, rest_url, public_key_pem, dependencies, wishlist, container_name, status, last_seen)
           VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11)"#,
    )
    .bind(&svc.id)
    .bind(&svc.name)
    .bind(&svc.version)
    .bind(&svc.ws_url)
    .bind(&svc.rest_url)
    .bind(&svc.public_key_pem)
    .bind(&svc.dependencies)
    .bind(&svc.wishlist)
    .bind(&svc.container_name)
    .bind(&svc.status)
    .bind(now)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn get_service_by_name(pool: &SqlitePool, name: &str) -> Result<Option<ServiceRow>> {
    let row = sqlx::query_as::<_, ServiceRow>(
        r#"SELECT id, name, version, ws_url, rest_url, public_key_pem,
                  dependencies, wishlist, container_name, status, last_seen, offline_since
           FROM services WHERE name = ?1"#,
    )
    .bind(name)
    .fetch_optional(pool)
    .await?;
    Ok(row)
}

pub async fn update_service_heartbeat(pool: &SqlitePool, name: &str, status: &str) -> Result<()> {
    let now = chrono::Utc::now().timestamp();
    sqlx::query(
        r#"UPDATE services SET last_seen = ?1, status = ?2, offline_since = NULL WHERE name = ?3"#,
    )
    .bind(now)
    .bind(status)
    .bind(name)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn mark_service_offline(pool: &SqlitePool, name: &str, offline_type: &str) -> Result<()> {
    let now = chrono::Utc::now().timestamp();
    sqlx::query(
        r#"UPDATE services SET status = ?1, offline_since = COALESCE(offline_since, ?2) WHERE name = ?3"#,
    )
    .bind(offline_type)
    .bind(now)
    .bind(name)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn list_services(pool: &SqlitePool) -> Result<Vec<ServiceRow>> {
    let rows = sqlx::query_as::<_, ServiceRow>(
        r#"SELECT id, name, version, ws_url, rest_url, public_key_pem,
                  dependencies, wishlist, container_name, status, last_seen, offline_since
           FROM services"#,
    )
    .fetch_all(pool)
    .await?;
    Ok(rows)
}
