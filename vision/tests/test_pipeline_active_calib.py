from store import db as dbmod, repo
from vision.threed.calibration import active_calibration, CheckerboardCalibration


def test_active_calibration_prefers_stored_then_falls_back():
    conn = dbmod.connect(":memory:"); dbmod.init_db(conn=conn)
    # none stored -> AssumedGeometry fallback when dims given
    cal = active_calibration(conn, image_width=1214, image_height=1284)
    assert cal is not None and cal.__class__.__name__ == "AssumedGeometryCalibration"
    # store one -> CheckerboardCalibration returned
    repo.save_calibration(conn, device_index=0, cols=9, rows=6, square_mm=25.0,
                          n_poses=20, reprojection_error=0.4,
                          calib_json='{"image_width":640,"image_height":480,'
                          '"K_face_on":[[800,0,320],[0,800,240],[0,0,1]],'
                          '"K_down_line":[[800,0,320],[0,800,240],[0,0,1]],'
                          '"R_face_on":[[1,0,0],[0,1,0],[0,0,1]],"t_face_on":[0,0,0],'
                          '"R_down_line":[[1,0,0],[0,1,0],[0,0,1]],"t_down_line":[0,0,0.5],'
                          '"up":[0,-1,0],"target_line":[1,0,0],"depth":[0,0,1]}')
    cal2 = active_calibration(conn, image_width=1214, image_height=1284)
    assert isinstance(cal2, CheckerboardCalibration) and cal2.confidence == "high"
