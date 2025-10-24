use pbkdf2::pbkdf2_hmac;
use hmac::Hmac;
use sha2::Sha256;
use aes_gcm::{Aes256Gcm, Key, Nonce, KeyInit};
use aes_gcm::aead::{Aead};
use base64::{engine::general_purpose, Engine as _};
use std::{path::Path, fs};
use rcgen::{Certificate, CertificateParams, DistinguishedName, DnType, IsCa, BasicConstraints};
use pem::Pem;
use x509_parser::prelude::*;

pub fn init_ca(data_dir: &str, passphrase: &str) -> Result<(), Box<dyn std::error::Error>> {
    let key_path = Path::new(data_dir).join("ca_key.enc");
    let cert_path = Path::new(data_dir).join("ca_cert.pem");

    if key_path.exists() && cert_path.exists() {
        println!("CA exists - skipping generation");
        return Ok(());
    }

    println!("Generating CA keypair...");
    let mut params = CertificateParams::new(vec![]);
    let mut dn = DistinguishedName::new();
    dn.push(DnType::CommonName, "RuneCore Root CA");
    params.distinguished_name = dn;
    params.is_ca = IsCa::Ca(BasicConstraints::Unconstrained);
    params.not_before = rcgen::date_time_ymd(2025, 1, 1);
    params.not_after = rcgen::date_time_ymd(2035, 1, 1);
    let cert = Certificate::from_params(params)?;

    let key_pem = cert.serialize_private_key_pem();
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

fn derive_key(passphrase: &str) -> [u8; 32] {
    let salt = b"runecore_ca_salt";
    let mut derived = [0u8; 32];
    pbkdf2_hmac::<Hmac<Sha256>>(passphrase.as_bytes(), salt, 100_000, &mut derived);
    derived
}

fn load_encrypted_key(data_dir: &str, passphrase: &str) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    let key_path = Path::new(data_dir).join("ca_key.enc");
    let content = fs::read_to_string(key_path)?;
    let parts: Vec<&str> = content.split(':').collect();
    if parts.len() != 2 {
        return Err("Invalid key storage format".into());
    }
    let nonce = general_purpose::STANDARD.decode(parts[0])?;
    let ciphertext = general_purpose::STANDARD.decode(parts[1])?;

    let derived = derive_key(passphrase);
    let aes_key = Key::from_slice(&derived);
    let cipher = Aes256Gcm::new(aes_key);
    let plaintext = cipher.decrypt(Nonce::from_slice(&nonce), ciphertext.as_ref())?;
    Ok(plaintext)
}

pub fn sign_csr(data_dir: &str, passphrase: &str, csr_pem: &str, days_valid: u32) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    // load CA key and cert
    let ca_cert_path = Path::new(data_dir).join("ca_cert.pem");
    let ca_cert_pem = fs::read_to_string(&ca_cert_path)?;

    let key_pem = load_encrypted_key(data_dir, passphrase)?;
    let ca_key_pem = String::from_utf8_lossy(&key_pem).to_string();
    let ca_cert = rcgen::Certificate::from_pem(&ca_cert_pem)?;

    // parse CSR PEM
    let (_label, csr_bytes) = {
        let pem = pem::parse(csr_pem)?;
        (pem.tag, pem.contents)
    };

    let (_, csr) = x509_parser::parse_x509_certification_request(&csr_bytes)?;
    let subject = csr.request_info.subject.clone();

    // build signed cert using rcgen
    let mut params = CertificateParams::from_ca_cert_pem(&ca_cert_pem, ca_key_pem.as_str())?;
    // set subject alt names and subject
    params.distinguished_name = {
        let mut dn = rcgen::DistinguishedName::new();
        for rdn in subject.rdns.iter() {
            for aty in rdn.set.iter() {
                if let Some(attr) = aty.attr.get_value().as_str() {
                    dn.push(rcgen::DnType::CommonName, attr);
                }
            }
        }
        dn
    };
    params.not_before = rcgen::date_time_ymd(2025, 1, 1);
    params.not_after = rcgen::date_time_ymd(2025, 1, 1 + (days_valid as i32 / 365));

    let cert = rcgen::Certificate::from_params(params)?;
    let cert_pem = cert.serialize_pem_with_signer(&ca_cert)?;
    Ok(cert_pem.into_bytes())
}

pub fn ensure_server_cert(data_dir: &str, passphrase: &str) -> Result<(), Box<dyn std::error::Error>> {
    let server_cert_path = Path::new(data_dir).join("server_cert.pem");
    let server_key_path = Path::new(data_dir).join("server_key.enc");
    if server_cert_path.exists() && server_key_path.exists() {
        println!("Server cert exists - skipping generation");
        return Ok(());
    }

    // generate server rsa key
    let rsa = Rsa::generate(2048)?;
    let pkey = PKey::from_rsa(rsa)?;
    let priv_pem = pkey.private_key_to_pem_pkcs8()?;

    // create CSR
    let mut name_builder = X509NameBuilder::new()?;
    name_builder.append_entry_by_text("CN", "runecore.local")?;
    let name = name_builder.build();

    let mut req_builder = openssl::x509::X509ReqBuilder::new()?;
    req_builder.set_subject_name(&name)?;
    req_builder.set_pubkey(&pkey)?;
    req_builder.sign(&pkey, openssl::hash::MessageDigest::sha256())?;
    let csr = req_builder.build();
    let csr_pem = csr.to_pem()?;

    // sign csr using CA
    let cert_pem = sign_csr(data_dir, passphrase, std::str::from_utf8(&csr_pem)?, 365)?;

    // encrypt private key using same scheme
    let derived = derive_key(passphrase);
    let aes_key = Key::from_slice(&derived);
    let cipher = Aes256Gcm::new(aes_key);
    let mut nonce_bytes = [0u8; 12];
    getrandom::getrandom(&mut nonce_bytes)?;
    let nonce = Nonce::from_slice(&nonce_bytes);
    let ciphertext = cipher.encrypt(nonce, priv_pem.as_ref())?;
    let store = format!("{}:{}", general_purpose::STANDARD.encode(&nonce_bytes), general_purpose::STANDARD.encode(&ciphertext));

    fs::write(server_key_path, store)?;
    fs::write(server_cert_path, cert_pem)?;
    println!("Server cert + key generated and stored in {}", data_dir);
    Ok(())
}
