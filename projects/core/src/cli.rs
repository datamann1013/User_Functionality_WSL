use clap::{Parser, Subcommand};
use std::fs;
use std::path::Path;

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
}

pub fn run_command(cmd: Cli) -> anyhow::Result<()> {
    match cmd.command {
        Commands::InitPassphrase { data_dir } => {
            let dir = data_dir.unwrap_or_else(|| "./data".to_string());
            fs::create_dir_all(&dir)?;
            let pass = base64::engine::general_purpose::STANDARD.encode(uuid::Uuid::new_v4().to_string());
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
                        let p = base64::engine::general_purpose::STANDARD.encode(uuid::Uuid::new_v4().to_string());
                        fs::write(pass_path, &p)?;
                        p
                    }
                }
            };
            crate::ca::init_ca(&dir, &pass)?;
            crate::ca::ensure_server_cert(&dir, &pass)?;
            println!("Core initialized in {}", dir);
        }
    }
    Ok(())
}
