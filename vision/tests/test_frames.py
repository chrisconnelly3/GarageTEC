import numpy as np
from vision.frames import split_views, FrameSource, VideoFileSource
from vision import constants as C
from vision.tests.conftest import TEST_VIDEO, requires_video


def test_split_views_geometry_synthetic():
    # 100 wide, 40 tall fake frame; left half|right half at split=0.5
    frame = np.zeros((40, 100, 3), dtype=np.uint8)
    frame[:, :50] = 10   # left
    frame[:, 50:] = 20   # right
    crops = split_views(frame, split=0.5)
    assert set(crops) == {C.VIEW_DOWN_LINE, C.VIEW_FACE_ON}
    assert crops[C.VIEW_DOWN_LINE].shape == (40, 50, 3)
    assert crops[C.VIEW_FACE_ON].shape == (40, 50, 3)
    assert crops[C.VIEW_DOWN_LINE][0, 0, 0] == 10   # left came from left
    assert crops[C.VIEW_FACE_ON][0, 0, 0] == 20     # right came from right


def test_videofilesource_is_a_framesource():
    assert issubclass(VideoFileSource, FrameSource)


@requires_video
def test_videofilesource_yields_monotonic_both_view_crops():
    src = VideoFileSource(TEST_VIDEO, split=0.5)
    assert src.width == 1920 and src.height == 1080
    assert src.fps > 0
    samples = []
    for s in src.frames():
        samples.append(s)
        if len(samples) >= 5:
            break
    src.close()
    # indices and times strictly increasing
    assert [s.index for s in samples] == [0, 1, 2, 3, 4]
    assert all(samples[i].time_s < samples[i + 1].time_s for i in range(4))
    # both views present and each ~half width (960x1080 for the 1920-wide sample)
    for s in samples:
        dl = s.view_crops[C.VIEW_DOWN_LINE]
        fo = s.view_crops[C.VIEW_FACE_ON]
        assert dl.shape[0] == 1080 and fo.shape[0] == 1080
        assert abs(dl.shape[1] - 960) <= 1 and abs(fo.shape[1] - 960) <= 1
