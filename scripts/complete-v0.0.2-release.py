#!/usr/bin/env python3
"""Assemble muKsMaTT v0.0.2 packages from verified v0.0.1 assets and the PR#1 tested GUI.
Only the ADVANCED-tab UI and Debian package version metadata change. Never rebuild the engine.
"""
import argparse, hashlib, os, shutil, subprocess, tarfile, tempfile, zipfile
from pathlib import Path
OLD="0.0.0-dev"; NEW="0.0.2"; P="muKsMaTT"
ORIGINAL_SHA={
    f"{P}-{OLD}-Linux-amd64.deb":"16f9290f9247afe9eacaa4ff7a6e1f4fddd6fa1cd5a411e8bdead438994dd333",
    f"{P}-{OLD}-Linux-amd64.tar.gz":"4f570df849ac5a09b8c1ac8916806e6207010bd00bfc9c6c8c0c9ebfca3b46cf",
    f"{P}-{OLD}-Source.tar.gz":"7fb1be2acdae50f71d1522551732e95a073705f74f465f9308e301963e372472",
    f"{P}-{OLD}-Linux-Library-Sources.tar.gz":"5d6048d9d4ba1bc3289b897887e818ef369597d25c0a0c6f998db38b50d29ec5",
}
STANDALONE=f"{P}-{NEW}-PR1-Linux-amd64Standalone"
def hashfile(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for part in iter(lambda:f.read(4*1024*1024),b""): h.update(part)
    return h.hexdigest()
def run(*a,**kw): subprocess.run(a,check=True,**kw)
def expand(p,d):
    with tarfile.open(p,"r:gz") as a: a.extractall(d,filter="data")
def archive(p,root,name):
    with tarfile.open(p,"w:gz") as a: a.add(root/name,arcname=name)
def compare_unmodified(a,b,except_paths):
    a,b=Path(a),Path(b)
    paths_a={p.relative_to(a) for p in a.rglob("*") if p.is_file()}
    paths_b={p.relative_to(b) for p in b.rglob("*") if p.is_file()}
    if paths_a!=paths_b: raise RuntimeError(f"Unexpected added/deleted package files: {paths_a ^ paths_b}")
    for rel in paths_a-except_paths:
        x,y=a/rel,b/rel
        if x.is_symlink() or y.is_symlink():
            if not (x.is_symlink() and y.is_symlink() and os.readlink(x)==os.readlink(y)):
                raise RuntimeError(f"Symlink modified: {rel}")
        elif hashfile(x)!=hashfile(y): raise RuntimeError(f"Engine or library modified: {rel}")
def main():
    p=argparse.ArgumentParser()
    for key in ["original","gui","tested-standalone","patch","out"]:
        p.add_argument("--"+key,required=True,type=Path)
    a=vars(p.parse_args()); original=a["original"]; out=a["out"]; out.mkdir(parents=True,exist_ok=True)
    gui=a["gui"]; tested=a["tested_standalone"]
    for name,expected in ORIGINAL_SHA.items():
        got=hashfile(original/name)
        if got!=expected: raise RuntimeError(f"v0.0.1 original checksum mismatch {name}: {got}")
        print("Verified original",name,flush=True)
    if not gui.is_file() or not tested.is_file(): raise RuntimeError("Tested GUI or standalone missing")
    with tempfile.TemporaryDirectory(prefix="muksmatt-v002-") as temp:
        w=Path(temp)
        # The published source tarball receives only the reviewed Linux UI patch and new UI tests.
        s=w/"src";s.mkdir();expand(original/f"{P}-{OLD}-Source.tar.gz",s)
        root=s/f"{P}-{OLD}-Source"
        if not (root/"src/advanced_merger_ui_linux.go").is_file(): raise RuntimeError("Unexpected source layout")
        run("patch","--batch","--fuzz=0","-p1","-i",str(a["patch"].resolve()),cwd=root)
        srcname=f"{P}-{NEW}-Source";root.rename(s/srcname)
        archive(out/(srcname+".tar.gz"),s,srcname)
        # Repack .deb with the identical tested GUI, retaining all engine/library/CLI files.
        olddeb=w/"deb-original";newdeb=w/"deb-new"
        run("dpkg-deb","--raw-extract",str(original/f"{P}-{OLD}-Linux-amd64.deb"),str(olddeb))
        shutil.copytree(olddeb,newdeb,symlinks=True)
        gui_rel=Path("usr/lib/muksmatt/app/muksmatt-bin")
        if not (newdeb/gui_rel).is_file(): raise RuntimeError("Debian GUI missing")
        shutil.copy2(gui,newdeb/gui_rel)
        control=Path("DEBIAN/control");text=(newdeb/control).read_text()
        if "Version: 0.0.0~dev\n" not in text: raise RuntimeError("Unexpected original Debian version")
        (newdeb/control).write_text(text.replace("Version: 0.0.0~dev\n","Version: 0.0.2\n"))
        compare_unmodified(olddeb,newdeb,{gui_rel,control})
        deb=out/f"{P}-{NEW}-Linux-amd64.deb"
        run("dpkg-deb","--build","--root-owner-group",str(newdeb),str(deb))
        if subprocess.check_output(["dpkg-deb","--field",str(deb),"Version"],text=True).strip()!=NEW:
            raise RuntimeError("Bad Debian control version")
        check=w/"deb-check";run("dpkg-deb","--raw-extract",str(deb),str(check))
        compare_unmodified(olddeb,check,{gui_rel,control})
        if hashfile(check/gui_rel)!=hashfile(gui): raise RuntimeError("Wrong Debian GUI")
        print("Debian verified; CLI and all engine and runtime files unchanged",flush=True)
        # Repack portable tarball with tested GUI; other binaries remain byte-identical.
        portable=w/"portable";portable.mkdir()
        expand(original/f"{P}-{OLD}-Linux-amd64.tar.gz",portable)
        oldname=f"{P}-{OLD}-Linux-amd64";port=portable/oldname
        if not (port/"muksmatt").is_file(): raise RuntimeError("Unexpected portable layout")
        saved=w/"portable-original";shutil.copytree(port,saved,symlinks=True)
        shutil.copy2(gui,port/"muksmatt")
        readme=port/"README-LINUX.txt"
        if readme.is_file(): readme.write_text(readme.read_text().replace(OLD,NEW))
        compare_unmodified(saved,port,{Path("muksmatt"),Path("README-LINUX.txt")})
        newname=f"{P}-{NEW}-Linux-amd64";port.rename(portable/newname)
        tarpath=out/(newname+".tar.gz");archive(tarpath,portable,newname)
        with tarfile.open(tarpath,"r:gz") as tar:
            member=tar.extractfile(newname+"/muksmatt")
            if member is None or hashlib.sha256(member.read()).hexdigest()!=hashfile(gui):
                raise RuntimeError("Wrong portable GUI")
        print("Portable verified; CLI and engine unchanged",flush=True)
        # Bundled library SOURCE code is unaffected by this GUI-only change.
        libs=out/f"{P}-{NEW}-Linux-Library-Sources.tar.gz"
        shutil.copy2(original/f"{P}-{OLD}-Linux-Library-Sources.tar.gz",libs)
        if hashfile(libs)!=ORIGINAL_SHA[f"{P}-{OLD}-Linux-Library-Sources.tar.gz"]:
            raise RuntimeError("Bundled library sources changed")
        shutil.copy2(tested,out/STANDALONE)
        if hashfile(out/STANDALONE)!=hashfile(tested): raise RuntimeError("Standalone changed")
    assets=[f"{P}-{NEW}-Linux-amd64.deb",f"{P}-{NEW}-Linux-amd64.tar.gz",
            f"{P}-{NEW}-Source.tar.gz",f"{P}-{NEW}-Linux-Library-Sources.tar.gz",STANDALONE]
    sums=out/"SHA256SUMS.txt"
    sums.write_text("".join(f"{hashfile(out/n)}  {n}\n" for n in assets))
    # The dev ZIP is a rollup of all complete Linux v0.0.2 packages.
    zipname=f"{P}-Linux-amd64-dev.zip"
    with zipfile.ZipFile(out/zipname,"w",zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
        for n in assets+["SHA256SUMS.txt"]: z.write(out/n,arcname=n)
    with zipfile.ZipFile(out/zipname) as z:
        if z.testzip() is not None: raise RuntimeError("Corrupt dev ZIP")
        if set(z.namelist())!=set(assets+["SHA256SUMS.txt"]): raise RuntimeError("Incomplete dev ZIP")
    sums.write_text("".join(f"{hashfile(out/n)}  {n}\n" for n in assets+[zipname]))
    for name in assets+[zipname,"SHA256SUMS.txt"]:
        print(name,(out/name).stat().st_size,hashfile(out/name),flush=True)
if __name__=="__main__": main()
