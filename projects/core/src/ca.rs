use openssl::rsa::Rsa;
use openssl::x509::{X509NameBuilder, X509};
use openssl::pkey::PKey;
use openssl::x509::X509Builder;
use pbkdf2::pbkdf2_hmac;
use hmac::Hmac;
use sha2::Sha256;
use aes_gcm::{Aes256Gcm, Key, Nonce};
use aes_gcm::aead::{Aead, NewAead};
use base64::{engine::general_purpose, Engine as _};
use std::{path::Path, fs};

pub fn init_ca(data_dir: &str, passphrase: &str) -> Result<(), Box<dyn std::error::Error>> {
    let key_path = Path::new(data_dir).join("ca_key.enc");
    let cert_path = Path::new(data_dir).join("ca_cert.pem");

    if key_path.exists() && cert_path.exists() {
        println!("CA exists - skipping generation");
        return Ok(());
    }

    println!("Generating CA keypair...");
    let rsa = Rsa::generate(2048)?;
    let pkey = PKey::from_rsa(rsa)?;

    // create self-signed cert
    let mut name_builder = X509NameBuilder::new()?;
    name_builder.append_entry_by_text("CN", "RuneCore Root CA")?;
    let name = name_builder.build();

    let mut builder = X509Builder::new()?;
    builder.set_subject_name(&name)?;
    builder.set_issuer_name(&name)?;
    builder.set_pubkey(&pkey)?;
    builder.set_not_before(&openssl::asn1::Asn1Time::days_from_now(0)?)?;
    builder.set_not_after(&openssl::asn1::Asn1Time::days_from_now(3650)?)?; // 10 years
    builder.sign(&pkey, openssl::hash::MessageDigest::sha256())?;
    let cert: X509 = builder.build();

    let key_pem = pkey.private_key_to_pem_pkcs8()?;
    let cert_pem = cert.to_pem()?;

    // derive key from passphrase
    let salt = b"runecore_ca_salt";
    let mut derived = [0u8; 32];
    pbkdf2_hmac::<Hmac<Sha256>>(passphrase.as_bytes(), salt, 100_000, &mut derived);

    let aes_key = Key::from_slice(&derived);
    let cipher = Aes256Gcm::new(aes_key);

    // random nonce
    let mut nonce_bytes = [0u8; 12];
    getrandom::getrandom(&mut nonce_bytes)?;
    let nonce = Nonce::from_slice(&nonce_bytes);

    let ciphertext = cipher.encrypt(nonce, key_pem.as_ref())?;

    // store nonce + ciphertext as base64
    let store = format!("{}:{}", general_purpose::STANDARD.encode(&nonce_bytes), general_purpose::STANDARD.encode(&ciphertext));
    fs::write(key_path, store)?;
    fs::write(cert_path, cert_pem)?;

    println!("CA initialized and stored in {}", data_dir);
    Ok(())
}
