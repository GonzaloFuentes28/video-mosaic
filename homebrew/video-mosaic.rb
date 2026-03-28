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
  url "https://github.com/GonzaloFuentes28/video-mosaic/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "df16333a1f63084cb9b3f86ca37a82a5682bc8806d8a754351746a261ae64385"
  license "MIT"

  depends_on "ffmpeg"
  depends_on "python@3.12"

  resource "pillow" do
    url "https://files.pythonhosted.org/packages/source/p/pillow/pillow-12.1.1.tar.gz"
    sha256 "9ad8fa5937ab05218e2b6a4cff30295ad35afd2f83ac592e68c0d871bb0fdbc4"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/source/r/rich/rich-14.3.3.tar.gz"
    sha256 "b8daa0b9e4eef54dd8cf7c86c03713f53241884e814f4e2f5fb342fe520f639b"
  end

  resource "markdown-it-py" do
    url "https://files.pythonhosted.org/packages/source/m/markdown-it-py/markdown_it_py-4.0.0.tar.gz"
    sha256 "cb0a2b4aa34f932c007117b194e945bd74e0ec24133ceb5bac59009cda1cb9f3"
  end

  resource "mdurl" do
    url "https://files.pythonhosted.org/packages/source/m/mdurl/mdurl-0.1.2.tar.gz"
    sha256 "bb413d29f5eea38f31dd4754dd7377d4465116fb207585f97bf925588687c1ba"
  end

  resource "pygments" do
    url "https://files.pythonhosted.org/packages/source/p/pygments/pygments-2.19.2.tar.gz"
    sha256 "636cb2477cec7f8952536970bc533bc43743542f70392ae026374600add5b887"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "usage", shell_output("#{bin}/video-mosaic --help")
  end
end
