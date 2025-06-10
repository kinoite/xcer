#!/usr/bin/env python

# xcbuild -- tool to help users package stuff for xcer

import os
import tarfile
import argparse
import io

SOURCE_DIR = 'source_packages'
OUTPUT_DIR = 'remote_repo_server'

def create_package(package_name, version, dependencies):
    """
    Creates a FHS-compliant .tar.gz package.
    """
    source_path = os.path.join(SOURCE_DIR, package_name)

    if not os.path.isdir(source_path):
        print(f"❌ Error: Source directory not found at '{source_path}'")
        return

    print(f"-> Building {package_name} version {version} as .tar.gz...")

    archive_name = f"{package_name}-{version}.tar.gz"
    compressed_archive_path = os.path.join(OUTPUT_DIR, archive_name)

    try:

        with tarfile.open(compressed_archive_path, "w:gz") as tf:

            pkginfo_content = f"name = {package_name}\n"
            pkginfo_content += f"version = {version}\n"
            if dependencies:
                for dep in dependencies:
                    pkginfo_content += f"depend = {dep}\n"

            file_list = []
            for root, dirs, files in os.walk(source_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, source_path)
                    file_list.append(relative_path)

            pkginfo_content += "\n".join([f"file = {f}" for f in sorted(file_list)])

            pkginfo_bytes = pkginfo_content.encode('utf-8')
            tarinfo = tarfile.TarInfo(name=".PKGINFO")
            tarinfo.size = len(pkginfo_bytes)
            tf.addfile(tarinfo, io.BytesIO(pkginfo_bytes))

            tf.add(source_path, arcname='.')

        print(f"✅ Successfully created {compressed_archive_path}")

    except Exception as e:
        print(f"❌ An error occurred during build: {e}")

def main():
    """Parses command-line arguments."""

    parser = argparse.ArgumentParser(description="Xcer Build Tool: Creates .tar.gz packages.")
    parser.add_argument("package_name", help="The name of the package to build.")
    parser.add_argument("--version", required=True, help="The version of the package.")
    parser.add_argument("--depends", action="append", help="A package dependency.")
    args = parser.parse_args()

    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)

    create_package(args.package_name, args.version, args.depends or [])

if __name__ == "__main__":
    main()
