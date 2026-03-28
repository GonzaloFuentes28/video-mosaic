# This file goes in a separate repo: github.com/GonzaloFuentes28/homebrew-tap
# File path: Formula/video-mosaic.rb
#
# Users install with:
#   brew tap GonzaloFuentes28/tap
#   brew install video-mosaic

class VideoMosaic < Formula
  include Language::Python::Virtualenv

  desc "Extract video frames and compose them into a mosaic image"
  homepage "https://github.com/GonzaloFuentes28/video-mosaic"
  # ⚠️  Update URL + sha256 for each release
  url "https://github.com/GonzaloFuentes28/video-mosaic/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "REPLACE_WITH_ACTUAL_SHA256"
  license "MIT"

  depends_on "ffmpeg"
  depends_on "python@3.12"

  resource "pillow" do
    url "https://files.pythonhosted.org/packages/source/p/pillow/pillow-11.1.0.tar.gz"
    sha256 "REPLACE_WITH_ACTUAL_SHA256"
  end

  resource "tqdm" do
    url "https://files.pythonhosted.org/packages/source/t/tqdm/tqdm-4.67.1.tar.gz"
    sha256 "REPLACE_WITH_ACTUAL_SHA256"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "usage", shell_output("#{bin}/video-mosaic --help")
  end
end
