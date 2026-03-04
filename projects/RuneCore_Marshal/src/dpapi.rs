//! Windows DPAPI (Data Protection API) wrapper.
//!
//! Used to encrypt the Marshal private key at rest so that even if the file
//! is copied off the machine it cannot be decrypted on a different host.
//!
//! Encryption scope: CRYPTPROTECT_LOCAL_MACHINE
//!   - Any process running on *this machine* can decrypt.
//!   - The certs/ directory ACL (SYSTEM + Administrators only) restricts
//!     who can read the file, providing the additional access-control layer.
//!
//! This module compiles only on Windows. On other platforms the bootstrap
//! falls back to writing a plain PEM key file.

#[cfg(target_os = "windows")]
mod inner {
    use std::ptr;
    use winapi::shared::minwindef::FALSE;
    use winapi::um::dpapi::{
        CryptProtectData, CryptUnprotectData, CRYPTPROTECT_LOCAL_MACHINE,
    };
    use winapi::um::wincrypt::DATA_BLOB;
    use winapi::um::winbase::LocalFree;

    /// DPAPI-encrypt `data` with machine scope.
    /// Returns the opaque encrypted blob.
    pub fn protect(data: &[u8]) -> Result<Vec<u8>, String> {
        unsafe {
            let mut input = DATA_BLOB {
                cbData: data.len() as u32,
                pbData: data.as_ptr() as *mut u8,
            };
            let mut output = DATA_BLOB {
                cbData: 0,
                pbData: ptr::null_mut(),
            };
            let result = CryptProtectData(
                &mut input,
                ptr::null(),         // no description string
                ptr::null_mut(),     // no optional entropy
                ptr::null_mut(),     // reserved
                ptr::null_mut(),     // no UI prompt
                CRYPTPROTECT_LOCAL_MACHINE,
                &mut output,
            );
            if result == FALSE {
                return Err(format!(
                    "CryptProtectData failed: {}",
                    std::io::Error::last_os_error()
                ));
            }
            let blob =
                std::slice::from_raw_parts(output.pbData, output.cbData as usize).to_vec();
            LocalFree(output.pbData as *mut winapi::ctypes::c_void);
            Ok(blob)
        }
    }

    /// DPAPI-decrypt a blob previously produced by `protect`.
    pub fn unprotect(data: &[u8]) -> Result<Vec<u8>, String> {
        unsafe {
            let mut input = DATA_BLOB {
                cbData: data.len() as u32,
                pbData: data.as_ptr() as *mut u8,
            };
            let mut output = DATA_BLOB {
                cbData: 0,
                pbData: ptr::null_mut(),
            };
            let result = CryptUnprotectData(
                &mut input,
                ptr::null_mut(), // discard description
                ptr::null_mut(), // no optional entropy
                ptr::null_mut(), // reserved
                ptr::null_mut(), // no UI prompt
                0,               // flags (user scope for decrypt; machine-encrypted can be decrypted by any user on machine)
                &mut output,
            );
            if result == FALSE {
                return Err(format!(
                    "CryptUnprotectData failed: {}",
                    std::io::Error::last_os_error()
                ));
            }
            let plain =
                std::slice::from_raw_parts(output.pbData, output.cbData as usize).to_vec();
            LocalFree(output.pbData as *mut winapi::ctypes::c_void);
            Ok(plain)
        }
    }
}

#[cfg(target_os = "windows")]
pub use inner::{protect, unprotect};
