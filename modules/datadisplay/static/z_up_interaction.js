(() => {
  const vtk = window.vtk;
  const styles = vtk?.Interaction?.Style;
  const manipulators = vtk?.Interaction?.Manipulators;
  const trackballStyle = styles?.vtkInteractorStyleTrackballCamera;

  if (!trackballStyle || !styles.vtkInteractorStyleManipulator || !manipulators) {
    throw new Error("Panel's vtk.js interaction APIs are unavailable.");
  }

  if (trackballStyle.newInstance.zUpInstalled) {
    return;
  }

  const createZUpStyle = () => {
    const style = styles.vtkInteractorStyleManipulator.newInstance();
    const rotate = manipulators.vtkMouseCameraTrackballRotateManipulator.newInstance({
      button: 1,
      useWorldUpVec: true,
      worldUpVec: [0, 0, 1],
      useFocalPointAsCenterOfRotation: true,
    });
    const pan = manipulators.vtkMouseCameraTrackballPanManipulator.newInstance({
      button: 2,
    });
    const shiftPan = manipulators.vtkMouseCameraTrackballPanManipulator.newInstance({
      button: 1,
      shift: true,
    });
    const zoom = manipulators.vtkMouseCameraTrackballZoomManipulator.newInstance({
      button: 3,
    });
    const wheelZoom = manipulators.vtkMouseCameraTrackballZoomManipulator.newInstance({
      dragEnabled: false,
      scrollEnabled: true,
    });

    style.addMouseManipulator(rotate);
    style.addMouseManipulator(pan);
    style.addMouseManipulator(shiftPan);
    style.addMouseManipulator(zoom);
    style.addMouseManipulator(wheelZoom);
    return style;
  };

  createZUpStyle.zUpInstalled = true;
  trackballStyle.newInstance = createZUpStyle;
})();