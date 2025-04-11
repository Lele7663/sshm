# Maintainer: lele7663 <your.email@example.com>
pkgname=sshm
pkgver=0.1.0
pkgrel=1
pkgdesc="A modern, user-friendly TUI for managing SSH connections"
arch=('any')
url="https://github.com/lele7663/sshm"
license=('MIT')
depends=('python>=3.8' 'python-textual' 'python-cryptography' 'python-paramiko' 'sshpass')
makedepends=('python-setuptools')
source=("$pkgname-$pkgver.tar.gz::https://github.com/lele7663/sshm/archive/v$pkgver.tar.gz")
sha256sums=('SKIP')  # You'll need to replace this with actual checksum

build() {
  cd "$pkgname-$pkgver"
  python setup.py build
}

package() {
  cd "$pkgname-$pkgver"
  python setup.py install --root="$pkgdir" --optimize=1 --skip-build
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
} 