// build.rs — optionally link against droidB-thor's odin4_c C ABI (its own
// include/odin4/odin4_c.h / libodin4.so, shipped as part of that library — see
// thearxos/droidB-thor for why this exists: the library's original odin4.h passes
// std::string/std::vector directly through an `extern "C"` boundary, which is not actually a
// stable ABI; odin4_c.h is the real, primitive-only C surface added alongside it).
//
// This is intentionally OPTIONAL and never fails the build. droidB-native ships as one
// portable binary; hard-linking libodin4.so at compile time would make that binary refuse to
// even start on any machine where droidB-thor is not installed, breaking every OTHER droidB
// feature for users who only want ADB/hardening/debloat. Absent the library, `samsung.rs`
// falls back to driving the `odin4` CLI as a subprocess — same graceful-optional pattern
// already used for mtkclient/edl in engines.rs.
//
// Override points (for a controlled build host, e.g. this repo's own CI, that has
// droidB-thor's build tree rather than its installed package): set ODIN4_INCLUDE_DIR /
// ODIN4_LIB_DIR.
use std::env;
use std::path::{Path, PathBuf};

fn main() {
    println!("cargo:rerun-if-env-changed=ODIN4_INCLUDE_DIR");
    println!("cargo:rerun-if-env-changed=ODIN4_LIB_DIR");
    // required so `#[cfg(thor_ffi)]` doesn't trigger the unexpected-cfg lint under -D warnings
    println!("cargo::rustc-check-cfg=cfg(thor_ffi)");

    let include_dir = env::var("ODIN4_INCLUDE_DIR").ok().map(PathBuf::from).or_else(find_system_include);
    let lib_dir = env::var("ODIN4_LIB_DIR").ok().map(PathBuf::from).or_else(find_system_lib);

    let (Some(include_dir), Some(lib_dir)) = (include_dir, lib_dir) else {
        // Not found: this is normal, not an error. droidB-native builds fine without it.
        println!("cargo:warning=droidB-thor (libodin4) not found — Samsung flashing will use the odin4 CLI subprocess path instead of linked FFI. Install droidB-thor, or set ODIN4_INCLUDE_DIR/ODIN4_LIB_DIR, to build with FFI.");
        return;
    };
    if !include_dir.join("odin4").join("odin4_c.h").is_file() {
        println!("cargo:warning=found libodin4 but not odin4_c.h — this droidB-thor build predates the C ABI shim. Falling back to the CLI path.");
        return;
    }

    println!("cargo:rustc-link-search=native={}", lib_dir.display());
    println!("cargo:rustc-link-lib=dylib=odin4");
    println!("cargo:rustc-cfg=thor_ffi");
    let _ = include_dir; // the crate only calls already-compiled odin4_c symbols; no local C++ compile needed
}

fn find_system_include() -> Option<PathBuf> {
    let p = Path::new("/usr/include/odin4/odin4.h");
    p.is_file().then(|| PathBuf::from("/usr/include"))
}

fn find_system_lib() -> Option<PathBuf> {
    for dir in ["/usr/lib", "/usr/lib64", "/usr/local/lib"] {
        if Path::new(dir).join("libodin4.so").exists() { return Some(PathBuf::from(dir)); }
    }
    None
}
