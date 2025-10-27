use anyhow::Result;
use std::path::Path;

#[tokio::test]
async fn ca_init_and_sign() -> Result<()> {
    // Create a temp directory for the test
    let tmp = tempfile::tempdir()?;
    let dir = tmp.path().to_str().unwrap().to_string();

    // init CA
    crate::ca::init_ca(&dir, "test-pass")?;
    assert!(Path::new(&dir).join("ca_cert.pem").exists());
    assert!(Path::new(&dir).join("ca_key.enc").exists());

    // create a CSR programmatically
    let rsa = openssl::rsa::Rsa::generate(1024)?;
    let pkey = openssl::pkey::PKey::from_rsa(rsa)?;
    let mut name_builder = openssl::x509::X509NameBuilder::new()?;
    name_builder.append_entry_by_text("CN", "test-client")?;
    let name = name_builder.build();

    let mut req_builder = openssl::x509::X509ReqBuilder::new()?;
    req_builder.set_subject_name(&name)?;
    req_builder.set_pubkey(&pkey)?;
    req_builder.sign(&pkey, openssl::hash::MessageDigest::sha256())?;
    let csr = req_builder.build();
    let csr_pem = String::from_utf8(csr.to_pem()?)?;

    // sign CSR
    let cert_pem = crate::ca::sign_csr_with_role(&dir, "test-pass", &csr_pem, 365, "client")?;
    let cert_str = String::from_utf8_lossy(&cert_pem);
    assert!(cert_str.contains("BEGIN CERTIFICATE"));
    Ok(())
}
