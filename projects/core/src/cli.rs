use clap::{Parser, Subcommand};
use std::fs;
use std::path::Path;
use anyhow::Result;

#[derive(Parser)]
#[command(author, version, about = "RuneCore Core CLI helpers")]
pub struct Cli {
    #[command(subcommand)]
    pub command: Commands,
}

#[derive(Subcommand)]
pub enum Commands {
    /// Initialize passphrase file under data dir
    InitPassphrase {
        /// data directory (defaults to ./data)
        #[arg(short, long)]
        data_dir: Option<String>,
    },
    /// Initialize core (CA + server cert)
    InitCore {
        #[arg(short, long)]
        data_dir: Option<String>,
        #[arg(short, long)]
        passphrase: Option<String>,
    },
    /// Sign a CSR file using the core CA
    SignCsr {
        /// data directory (defaults to ./data)
        #[arg(short, long)]
        data_dir: Option<String>,
        /// path to CSR file to sign (PEM)
        #[arg(short, long)]
        csr_file: String,
        /// output path for signed cert (defaults to data/client_cert.pem)
        #[arg(short, long)]
        out: Option<String>,
        /// validity days
        #[arg(short, long)]
        days: Option<u32>,
    },
}

pub fn run_command(cmd: Cli) -> Result<()> {
    match cmd.command {
        Commands::InitPassphrase { data_dir } => {
            let dir = data_dir.unwrap_or_else(|| "./data".to_string());
            fs::create_dir_all(&dir)?;
            let pass = uuid::Uuid::new_v4().to_string();
            let pass_path = Path::new(&dir).join("ca_passphrase.txt");
            fs::write(pass_path, pass)?;
            println!("Wrote passphrase to {}", dir);
        }
        Commands::InitCore { data_dir, passphrase } => {
            let dir = data_dir.unwrap_or_else(|| "./data".to_string());
            fs::create_dir_all(&dir)?;
            let pass = match passphrase {
                Some(p) => p,
                None => {
                    let pass_path = Path::new(&dir).join("ca_passphrase.txt");
                    if pass_path.exists() {
                        fs::read_to_string(pass_path)?
                    } else {
                        let p = uuid::Uuid::new_v4().to_string();
                        fs::write(pass_path, &p)?;
                        p
                    }
                }
            };
            crate::ca::init_ca(&dir, &pass)?;
            crate::ca::ensure_server_cert(&dir, &pass)?;
            println!("Core initialized in {}", dir);
        }
        Commands::SignCsr { data_dir, csr_file, out, days } => {
            let dir = data_dir.unwrap_or_else(|| "./data".to_string());
            fs::create_dir_all(&dir)?;
            let pass_path = Path::new(&dir).join("ca_passphrase.txt");
            if !pass_path.exists() {
                return Err(anyhow::anyhow!("passphrase file not found; run InitCore first"));
            }
            let pass = fs::read_to_string(pass_path)?;
            let csr_pem = fs::read_to_string(&csr_file)?;
            let days_valid = days.unwrap_or(365);
            let cert_bytes = crate::ca::sign_csr(&dir, &pass, &csr_pem, days_valid)?;
            let out_path = match out {
                Some(p) => p,
                None => Path::new(&dir).join("client_cert.pem").to_string_lossy().to_string(),
            };
            fs::write(out_path, cert_bytes)?;
            println!("Signed CSR and wrote cert to data dir");
        }
    }
    Ok(())
}
