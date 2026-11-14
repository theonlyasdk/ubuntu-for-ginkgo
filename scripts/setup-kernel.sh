#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/env.sh
source "$ROOT/scripts/env.sh"

TAG="${KERNEL_TAG:-v7.0}"

if [[ -d "$KERNEL_SRC/.git" ]]; then
	echo "Kernel source already present at $KERNEL_SRC"
	exit 0
fi

echo "==> Cloning Linux $TAG (shallow)..."
git clone --depth 1 --branch "$TAG" \
	https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git \
	"$KERNEL_SRC"

if [[ -d "$ROOT/overlays/linux" ]]; then
	echo "==> Applying overlays/linux"
	cp -a "$ROOT/overlays/linux/arch" "$KERNEL_SRC/" 2>/dev/null || true
	cp -a "$ROOT/overlays/linux/drivers" "$KERNEL_SRC/" 2>/dev/null || true
	for p in "$ROOT/overlays/linux/"*.patch; do
		if [[ -f "$p" ]]; then
			echo "Applying patch: $(basename "$p")"
			patch -d "$KERNEL_SRC" -p1 -N -r - < "$p" || true
		fi
	done
fi

echo "==> ginkgo DTS:"
ls -la "$KERNEL_SRC/arch/arm64/boot/dts/qcom/sm6125-xiaomi-ginkgo"* 2>/dev/null || true
