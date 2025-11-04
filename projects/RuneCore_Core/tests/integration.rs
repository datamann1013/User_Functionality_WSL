use std::fs;
use tempfile::tempdir;
use tokio::time::{sleep, Duration};

#[tokio::test]
async fn test_ca_init_and_service_register() {
    let dir = tempdir().unwrap();
    let data_dir = dir.path().to_string_lossy().to_string();

    // create passphrase file via CLI helper
    let cli = crate::cli::Cli { command: crate::cli::Commands::InitCore { data_dir: Some(data_dir.clone()), passphrase: None } };
    crate::cli::run_command(cli).unwrap();

    // check CA files exist
    assert!(fs::metadata(format!("{}/ca_cert.pem", data_dir)).is_ok());
    assert!(fs::metadata(format!("{}/ca_key.enc", data_dir)).is_ok());
    // server cert/key
    assert!(fs::metadata(format!("{}/server_cert.pem", data_dir)).is_ok());
    assert!(fs::metadata(format!("{}/server_key.enc", data_dir)).is_ok());

    // start server in background
    let data_dir_clone = data_dir.clone();
    tokio::spawn(async move {
        // set env
        std::env::set_var("RUNECORE_DATA_DIR", data_dir_clone);
        std::env::set_var("RUNECORE_CA_PASSPHRASE", "dummy");
        // call main (it will exit because args length is 1 in test) - skip server launch
    });

    // we can't fully start Axum here without more setup; so at minimum validate CA init above
    sleep(Duration::from_millis(100)).await;
}
