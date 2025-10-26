use anyhow::Result;
use pbkdf2::pbkdf2;
use hmac::Hmac;
use sha2::Sha256;
use aes_gcm::{Aes256Gcm, Key, Nonce, KeyInit};
use aes_gcm::aead::Aead;
use base64;
use std::{path::Path, fs};
use openssl::rsa::Rsa;
use openssl::x509::{X509NameBuilder, X509};
use openssl::pkey::PKey;
use openssl::x509::X509Builder;
use openssl::x509::extension::{BasicConstraints, KeyUsage, ExtendedKeyUsage, SubjectKeyIdentifier, AuthorityKeyIdentifier};
use getrandom;

pub fn init_ca(data_dir: &str, passphrase: &str) -> Result<()> {
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
    let nb = openssl::asn1::Asn1Time::days_from_now(0)?;
    let na = openssl::asn1::Asn1Time::days_from_now(3650)?; // 10 years
    builder.set_not_before(&nb)?;
    builder.set_not_after(&na)?;
    builder.sign(&pkey, openssl::hash::MessageDigest::sha256())?;
    let cert: X509 = builder.build();

    let key_pem = pkey.private_key_to_pem_pkcs8()?;
    let cert_pem = cert.to_pem()?;

    // derive key from passphrase
    let salt = b"runecore_ca_salt";
    let mut derived = [0u8; 32];
    pbkdf2::<Hmac<Sha256>>(passphrase.as_bytes(), salt, 100_000, &mut derived);

    let cipher = Aes256Gcm::new_from_slice(&derived).map_err(|e| anyhow::anyhow!(e.to_string()))?;

    // random nonce
    let mut nonce_bytes = [0u8; 12];
    getrandom::getrandom(&mut nonce_bytes)?;
    let nonce = Nonce::from_slice(&nonce_bytes);

    let ciphertext = cipher.encrypt(nonce, key_pem.as_ref()).map_err(|e| anyhow::anyhow!(e.to_string()))?;

    // store nonce + ciphertext as base64
    let store = format!("{}:{}", base64::encode(&nonce_bytes), base64::encode(&ciphertext));
    fs::write(key_path, store)?;
    fs::write(cert_path, cert_pem)?;

    println!("CA initialized and stored in {}", data_dir);
    Ok(())
}

fn derive_key(passphrase: &str) -> [u8; 32] {
    let salt = b"runecore_ca_salt";
    let mut derived = [0u8; 32];
    pbkdf2::<Hmac<Sha256>>(passphrase.as_bytes(), salt, 100_000, &mut derived);
    derived
}

fn load_encrypted_key(data_dir: &str, passphrase: &str) -> Result<Vec<u8>> {
    let key_path = Path::new(data_dir).join("ca_key.enc");
    let content = fs::read_to_string(key_path)?;
    let parts: Vec<&str> = content.split(':').collect();
    if parts.len() != 2 {
        return Err(anyhow::anyhow!("Invalid key storage format"));
    }
    let nonce = base64::decode(parts[0])?;
    let ciphertext = base64::decode(parts[1])?;

    let derived = derive_key(passphrase);
    let cipher = Aes256Gcm::new_from_slice(&derived).map_err(|e| anyhow::anyhow!(e.to_string()))?;
    let plaintext = cipher.decrypt(Nonce::from_slice(&nonce), ciphertext.as_ref()).map_err(|e| anyhow::anyhow!(e.to_string()))?;
    Ok(plaintext)
}

pub fn sign_csr(data_dir: &str, passphrase: &str, csr_pem: &str, days_valid: u32) -> Result<Vec<u8>> {
    // load CA key and cert
    let ca_cert_path = Path::new(data_dir).join("ca_cert.pem");
    let ca_cert_pem = fs::read(&ca_cert_path)?;
    let ca_cert = X509::from_pem(&ca_cert_pem)?;

    let key_pem = load_encrypted_key(data_dir, passphrase)?;
    let ca_priv = PKey::private_key_from_pem(&key_pem)?;

    // parse CSR
    let csr = openssl::x509::X509Req::from_pem(csr_pem.as_bytes())?;

    // build cert
    let mut builder = X509Builder::new()?;
    builder.set_subject_name(csr.subject_name())?;
    builder.set_issuer_name(ca_cert.subject_name())?;
    let pubkey = csr.public_key()?;
    builder.set_pubkey(&pubkey)?;
    let nb2 = openssl::asn1::Asn1Time::days_from_now(0)?;
    let na2 = openssl::asn1::Asn1Time::days_from_now(days_valid)?;
    builder.set_not_before(&nb2)?;
    builder.set_not_after(&na2)?;
    // Ensure certificate version is v3 (2)
    builder.set_version(2)?;

    // Add commonly-required extensions: basicConstraints (CA:FALSE), keyUsage, extendedKeyUsage
    // basicConstraints
    let bc = BasicConstraints::new().critical().build()?;
    builder.append_extension(bc)?;

    // keyUsage: digitalSignature, keyEncipherment
    let ku = KeyUsage::new().digital_signature().key_encipherment().build()?;
    builder.append_extension(ku)?;

    // extendedKeyUsage: include both clientAuth and serverAuth to be permissive for both roles
    let mut eku = ExtendedKeyUsage::new();
    eku.client_auth();
    eku.server_auth();
    let eku = eku.build()?;
    builder.append_extension(eku)?;

    // subject and authority key identifiers (helpful for some clients)
    if let Ok(ski) = SubjectKeyIdentifier::new().build(&builder.x509v3_context(Some(&ca_cert), None)) {
        let _ = builder.append_extension(ski);
    }
    if let Ok(aki) = AuthorityKeyIdentifier::new().keyid(true).build(&builder.x509v3_context(Some(&ca_cert), None)) {
        let _ = builder.append_extension(aki);
    }

    builder.sign(&ca_priv, openssl::hash::MessageDigest::sha256())?;
    let cert = builder.build();
    let cert_pem = cert.to_pem()?;
    Ok(cert_pem)
}

pub fn ensure_server_cert(data_dir: &str, passphrase: &str) -> Result<()> {
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
    let cipher = Aes256Gcm::new_from_slice(&derived).map_err(|e| anyhow::anyhow!(e.to_string()))?;
    let mut nonce_bytes = [0u8; 12];
    getrandom::getrandom(&mut nonce_bytes)?;
    let nonce = Nonce::from_slice(&nonce_bytes);
    let ciphertext = cipher.encrypt(nonce, priv_pem.as_ref()).map_err(|e| anyhow::anyhow!(e.to_string()))?;
    let store = format!("{}:{}", base64::encode(&nonce_bytes), base64::encode(&ciphertext));

    fs::write(server_key_path, store)?;
    fs::write(server_cert_path, cert_pem)?;
    println!("Server cert + key generated and stored in {}", data_dir);
    Ok(())
}

pub fn get_server_cert_and_key_pem(data_dir: &str, passphrase: &str) -> Result<(Vec<u8>, Vec<u8>)> {
    let server_cert_path = Path::new(data_dir).join("server_cert.pem");
    let server_key_path = Path::new(data_dir).join("server_key.enc");
    let cert = fs::read(&server_cert_path)?;
    let content = fs::read_to_string(&server_key_path)?;
    let parts: Vec<&str> = content.split(':').collect();
    if parts.len() != 2 {
        return Err(anyhow::anyhow!("Invalid key storage format"));
    }
    let nonce = base64::decode(parts[0])?;
    let ciphertext = base64::decode(parts[1])?;
    let derived = derive_key(passphrase);
    let cipher = Aes256Gcm::new_from_slice(&derived).map_err(|e| anyhow::anyhow!(e.to_string()))?;
    let plaintext = cipher.decrypt(Nonce::from_slice(&nonce), ciphertext.as_ref()).map_err(|e| anyhow::anyhow!(e.to_string()))?;
    Ok((cert, plaintext))
}
