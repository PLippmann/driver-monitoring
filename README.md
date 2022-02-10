# all non-Carla code + Carla client scipts used for the driver monitoring project



**audio** contains all relevant files to the creation of the audio signal

**ddm** is the Drift-Diffusion implementation

**ezTrack** is the gaze tracker, which can be run via run.py but is also imported and run through the client scripts

**Carla** contains the client scripts, one based on PyGame and one based on the UE4 editor itself, to be run with a corresponding UE4 Carla server

The Carla version to be used: 0.9.12. The UE4 version to be used: 4.26 Carla branch



Running a simulation
-----------
1. Launch UE4 through `make launch` as instructed in Carla documentation, through the x64 native tools command line 
2. Select Map Town_04 (not Opt! You should see a floating camera on a highway onramp here) from the contents folder
3. Let everything load and all shaders compile before proceeding if this is your first time launching
4. In a terminal (on Windows a Powershell one) navigate to `carla\PythonAPI\examples` or wherever your Python client script is located
5. Press Play in UE4
6. Again, let everything compile if you see anything compiling
7. In the shell, execute the python client of your choice
8. In case you use a UE4 based simulation: click on the preview window in UE4 once the client is initialised and press X on your keyboard to attach the camera to the ego vehicle

NOTE: The changes made to Town_04 include the addition of the first person camera as a pawn, some backend logic to make this useable, as well as minor tweaks to make the map a more realistic driving experience. Further the vehicle blueprint to be used must have a working mirror. Such a mirror can be added to most cars through following the procedure outlined in `CarlaMirrorTutorial.pdf`.


TODO
-----------
Change Town04 to have proper onramp

Review mirror alignment and look into vehicle with larger mirror surface to replace 

Figure out loop in UE4
