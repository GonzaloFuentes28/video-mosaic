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
    url "https://files.pythonhosted.org/packages/source/p/pillow/pillow-11.1.0.tar.gz"
    sha256 "368da70808b36d73b4b390a8ffac11069f8a5c85f29eff1f1b01bcf3ef5b2a20"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/source/r/rich/rich-13.9.4.tar.gz"
    sha256 "439594978a49a09530cff7ebc4b5c7103ef57baf48d5ea3184f21d9a2befa098"
  end

  resource "markdown-it-py" do
    url "https://files.pythonhosted.org/packages/source/m/markdown-it-py/markdown-it-py-3.0.0.tar.gz"
    sha256 "e3f60a94fa066dc52ec76661e37c851cb232d92f9886b15cb560aaada2df8feb"
  end

  resource "mdurl" do
    url "https://files.pythonhosted.org/packages/source/m/mdurl/mdurl-0.1.2.tar.gz"
    sha256 "bb413d29f5eea38f31dd4754dd7377d4465116fb207585f97bf925588687c1ba"
  end

  resource "pygments" do
    url "https://files.pythonhosted.org/packages/source/p/pygments/pygments-2.19.1.tar.gz"
    sha256 "61c16d2a8576dc0649d9f39e089b5f02bcd27fba10d8fb4dcc28173f7a45151f"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "usage", shell_output("#{bin}/video-mosaic --help")
  end
end
