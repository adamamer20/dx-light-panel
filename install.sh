#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu
if [ "$(id -u)" -eq 0 ]; then
    echo "Run as your desktop user, not with sudo." >&2
    exit 1
fi
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cache="${XDG_CACHE_HOME:-$HOME/.cache}/dx-light-panel"
mkdir -p "$cache"
build_source() {
    source_name=$1
    repository=$2
    revision=$3
    directory="$cache/$source_name-$revision"
    if [ ! -d "$directory" ]; then
        mkdir "$directory"
        git -C "$directory" init -q
        git -C "$directory" fetch --depth 1 "$repository" "$revision"
        git -C "$directory" checkout --detach FETCH_HEAD
    fi
    if [ "$(git -C "$directory" rev-parse HEAD)" != "$revision" ] ||
       [ -n "$(git -C "$directory" status --porcelain --untracked-files=no)" ]; then
        echo "Cached upstream checkout changed: $directory. Use a fresh XDG_CACHE_HOME." >&2
        exit 1
    fi
}
build_source rgb-controller https://github.com/Hedriel/rgb-controller.git b10c3dc3df8cc3a28cd3146803d3df2d93c0332a
color_dir="$directory"
cmake -S "$color_dir" -B "$color_dir/build"
cmake --build "$color_dir/build" -j 4
build_source quiklight-x11 https://github.com/Kevinsillo/quiklight-x11.git 85c650c7220d6bd647b919e5c300b667b3259680
sync_dir="$directory"
cargo build --release --manifest-path "$sync_dir/Cargo.toml"
/usr/bin/python3 "$project_dir/install.py" "$color_dir/build/rgb-controller" "$sync_dir/target/release/quiklight"
