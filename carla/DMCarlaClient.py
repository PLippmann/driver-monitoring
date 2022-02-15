from pathlib import Path
import glob
import os
import sys
import argparse
from exp_info_ui import ExpInfoUI
import time
import csv
import cv2
from behav_helper import *
from ezTrack import Tracking

try:
    sys.path.append(glob.glob('../carla/dist/carla-*%d.%d-%s.egg' % (
        sys.version_info.major,
        sys.version_info.minor,
        'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
except IndexError:
    pass

import carla

try:
    import pygame
    from pygame.locals import KMOD_CTRL
    from pygame.locals import KMOD_SHIFT
    from pygame.locals import K_0
    from pygame.locals import K_9
    from pygame.locals import K_BACKQUOTE
    from pygame.locals import K_BACKSPACE
    from pygame.locals import K_COMMA
    from pygame.locals import K_DOWN
    from pygame.locals import K_ESCAPE
    from pygame.locals import K_F1
    from pygame.locals import K_LEFT
    from pygame.locals import K_PERIOD
    from pygame.locals import K_RIGHT
    from pygame.locals import K_SLASH
    from pygame.locals import K_SPACE
    from pygame.locals import K_TAB
    from pygame.locals import K_UP
    from pygame.locals import K_a
    from pygame.locals import K_b
    from pygame.locals import K_c
    from pygame.locals import K_d
    from pygame.locals import K_g
    from pygame.locals import K_h
    from pygame.locals import K_i
    from pygame.locals import K_l
    from pygame.locals import K_m
    from pygame.locals import K_n
    from pygame.locals import K_o
    from pygame.locals import K_p
    from pygame.locals import K_q
    from pygame.locals import K_r
    from pygame.locals import K_s
    from pygame.locals import K_t
    from pygame.locals import K_v
    from pygame.locals import K_w
    from pygame.locals import K_x
    from pygame.locals import K_z
    from pygame.locals import K_MINUS
    from pygame.locals import K_EQUALS
except ImportError:
    raise RuntimeError('cannot import pygame, make sure pygame package is installed')

try:
    import numpy as np
except ImportError:
    raise RuntimeError('cannot import numpy, make sure numpy package is installed')


import math
import time
import random
import numpy as np
import tkinter as tkr
import csv
import re



# ==============================================================================
# -- Global functions ----------------------------------------------------------
# ==============================================================================


def find_weather_presets():
    rgx = re.compile('.+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)')
    name = lambda x: ' '.join(m.group(0) for m in rgx.finditer(x))
    presets = [x for x in dir(carla.WeatherParameters) if re.match('[A-Z].+', x)]
    return [(getattr(carla.WeatherParameters, x), name(x)) for x in presets]


def get_actor_display_name(actor, truncate=250):
    name = ' '.join(actor.type_id.replace('_', '.').title().split('.')[1:])
    return (name[:truncate - 1] + u'\u2026') if len(name) > truncate else name

def get_actor_blueprints(world, filter, generation):
    bps = world.get_blueprint_library().filter(filter)
    print(bps)
    if generation.lower() == "all":
        return bps

    # If the filter returns only one bp, we assume that this one needed
    # and therefore, we ignore the generation
    if len(bps) == 1:
        return bps

    try:
        int_generation = int(generation)
        # Check if generation is in available generations
        if int_generation in [1, 2]:
            bps = [x for x in bps if int(x.get_attribute('generation')) == int_generation]
            return bps
        else:
            print("   Warning! Actor Generation is not valid. No actor will be spawned.")
            return []
    except:
        print("   Warning! Actor Generation is not valid. No actor will be spawned.")
        return []


# ==============================================================================
# -- World ---------------------------------------------------------------------
# ==============================================================================


class World(object):
    def __init__(self, carla_world, hud, args):
        self.world = carla_world
        self.sync = args.sync
        self.actor_role_name = args.rolename
        try:
            self.map = self.world.get_map()
        except RuntimeError as error:
            print('RuntimeError: {}'.format(error))
            print('  The server could not send the OpenDRIVE (.xodr) file:')
            print('  Make sure it exists, has the same name of your town, and is correct.')
            sys.exit(1)
        self.hud = hud
        self.player = None
        self.bot = None  #set up bot in world
        self.collision_sensor = None
        self.lane_invasion_sensor = None
        self.gnss_sensor = None
        self.imu_sensor = None
        self.radar_sensor = None
        self.camera_manager = None
        self._weather_presets = find_weather_presets()
        self._weather_index = 0
        self._actor_filter = "seat"#"prius"
        self._actor_generation = args.generation
        self._gamma = args.gamma
        self.restart()
        self.world.on_tick(hud.on_world_tick)
        self.recording_enabled = False
        self.recording_start = 0
        self.constant_velocity_enabled = False
        self.show_vehicle_telemetry = False
        self.doors_are_open = False
        self.current_map_layer = 0
        self.map_layer_names = [
            carla.MapLayer.NONE,
            carla.MapLayer.Buildings,
            carla.MapLayer.Decals,
            carla.MapLayer.Foliage,
            carla.MapLayer.Ground,
            carla.MapLayer.ParkedVehicles,
            carla.MapLayer.Particles,
            carla.MapLayer.Props,
            carla.MapLayer.StreetLights,
            carla.MapLayer.Walls,
            carla.MapLayer.All
        ]

    def restart(self):
        self.player_max_speed = 1.589
        self.player_max_speed_fast = 3.713
        # Keep same camera config if the camera manager exists.
        cam_index = self.camera_manager.index if self.camera_manager is not None else 0
        cam_pos_index = self.camera_manager.transform_index if self.camera_manager is not None else 0
        # Get a random blueprint.
        blueprint = random.choice(get_actor_blueprints(self.world, self._actor_filter, self._actor_generation))
        print("\nBlueprint: ", blueprint)
        blueprint.set_attribute('role_name', self.actor_role_name)
        if blueprint.has_attribute('color'):
            color = random.choice(blueprint.get_attribute('color').recommended_values)
            blueprint.set_attribute('color', color)
        if blueprint.has_attribute('driver_id'):
            driver_id = random.choice(blueprint.get_attribute('driver_id').recommended_values)
            blueprint.set_attribute('driver_id', driver_id)
        if blueprint.has_attribute('is_invincible'):
            blueprint.set_attribute('is_invincible', 'true')
        # set the max speed
        if blueprint.has_attribute('speed'):
            self.player_max_speed = float(blueprint.get_attribute('speed').recommended_values[1])
            self.player_max_speed_fast = float(blueprint.get_attribute('speed').recommended_values[2])
        '''
        # Spawn the player.
        if self.player is not None:
            spawn_point = self.player.get_transform()
            spawn_point.location.z += 2.0
            spawn_point.rotation.roll = 0.0
            spawn_point.rotation.pitch = 0.0
            self.destroy()
            self.player = self.world.try_spawn_actor(blueprint, spawn_point)
            self.show_vehicle_telemetry = False
            self.modify_vehicle_physics(self.player)
        while self.player is None:
            if not self.map.get_spawn_points():
                print('There are no spawn points available in your map/town.')
                print('Please add some Vehicle Spawn Point to your UE4 scene.')
                sys.exit(1)
            spawn_points = self.map.get_spawn_points()
            spawn_point = random.choice(spawn_points) if spawn_points else carla.Transform()
            spawn_point = carla.Transform(carla.Location(x = -99, y = 137, z = 3), carla.Rotation(yaw = 225))  #spawn point ego vehicle on ramp Town04
            self.player = self.world.try_spawn_actor(blueprint, spawn_point)
            self.show_vehicle_telemetry = False
            self.modify_vehicle_physics(self.player)

        # Spawn the bot.
        if self.bot is not None:
            spawn_point = self.bot.get_transform()
            spawn_point.location.z += 2.0
            spawn_point.rotation.roll = 0.0
            spawn_point.rotation.pitch = 0.0
            self.destroy()
            self.bot = self.world.try_spawn_actor(blueprint, spawn_point)
            self.show_vehicle_telemetry = False
            self.modify_vehicle_physics(self.bot)
        while self.bot is None:
            if not self.map.get_spawn_points():
                print('There are no spawn points available in your map/town.')
                print('Please add some Vehicle Spawn Point to your UE4 scene.')
                sys.exit(1)
            spawn_points = self.map.get_spawn_points()
            spawn_point = random.choice(spawn_points) if spawn_points else carla.Transform()
            spawn_point = carla.Transform(carla.Location(x = -220, y = 33.8, z = 11), carla.Rotation(yaw = 0.0))  #spawn point bot vehicle on highway Town04
            self.bot = self.world.try_spawn_actor(blueprint, spawn_point)
            self.show_vehicle_telemetry = False
            self.modify_vehicle_physics(self.bot)

        # Set up the sensors.
        self.collision_sensor = CollisionSensor(self.player, self.hud)
        self.lane_invasion_sensor = LaneInvasionSensor(self.player, self.hud)
        self.gnss_sensor = GnssSensor(self.player)
        self.imu_sensor = IMUSensor(self.player)
        self.camera_manager = CameraManager(self.player, self.hud, self._gamma)
        self.camera_manager.transform_index = cam_pos_index
        self.camera_manager.set_sensor(cam_index, notify=False)
        actor_type = get_actor_display_name(self.player)
        self.hud.notification(actor_type)
        '''
        if self.sync:
            self.world.tick()
        else:
            self.world.wait_for_tick()

    def next_weather(self, reverse=False):
        self._weather_index += -1 if reverse else 1
        self._weather_index %= len(self._weather_presets)
        preset = self._weather_presets[self._weather_index]
        self.hud.notification('Weather: %s' % preset[1])
        self.player.get_world().set_weather(preset[0])

    def next_map_layer(self, reverse=False):
        self.current_map_layer += -1 if reverse else 1
        self.current_map_layer %= len(self.map_layer_names)
        selected = self.map_layer_names[self.current_map_layer]
        self.hud.notification('LayerMap selected: %s' % selected)

    def load_map_layer(self, unload=False):
        selected = self.map_layer_names[self.current_map_layer]
        if unload:
            self.hud.notification('Unloading map layer: %s' % selected)
            self.world.unload_map_layer(selected)
        else:
            self.hud.notification('Loading map layer: %s' % selected)
            self.world.load_map_layer(selected)

    def modify_vehicle_physics(self, actor):
        #If actor is not a vehicle, we cannot use the physics control
        try:
            physics_control = actor.get_physics_control()
            physics_control.use_sweep_wheel_collision = True
            actor.apply_physics_control(physics_control)
        except Exception:
            pass

    def tick(self, clock):
        self.hud.tick(self, clock)

    def render(self, display):
        self.camera_manager.render(display)
        self.hud.render(display)

    def destroy_sensors(self):
        self.camera_manager.sensor.destroy()
        self.camera_manager.sensor = None
        self.camera_manager.index = None

    def destroy(self):
        if self.radar_sensor is not None:
            self.toggle_radar()
        sensors = [
            self.camera_manager.sensor,
            self.collision_sensor.sensor,
            self.lane_invasion_sensor.sensor,
            self.gnss_sensor.sensor,
            self.imu_sensor.sensor]
        for sensor in sensors:
            if sensor is not None:
                sensor.stop()
                sensor.destroy()
        if self.player is not None:
            self.player.destroy()
        if self.bot is not None:
            self.bot.destroy()



class KeyboardControl(object):
    """Class that handles keyboard input."""
    def __init__(self, world, start_in_autopilot):
        self._autopilot_enabled = start_in_autopilot
        if isinstance(world.player, carla.Vehicle):
            self._control = carla.VehicleControl()
            self._lights = carla.VehicleLightState.NONE
            world.player.set_autopilot(self._autopilot_enabled)
            world.player.set_light_state(self._lights)
        elif isinstance(world.player, carla.Walker):
            self._control = carla.WalkerControl()
            self._autopilot_enabled = False
            self._rotation = world.player.get_transform().rotation
        else:
            raise NotImplementedError("Actor type not supported")
        self._steer_cache = 0.0
        world.hud.notification("Press 'H' or '?' for help.", seconds=4.0)

    def parse_events(self, client, world, clock, sync_mode):
        if isinstance(self._control, carla.VehicleControl):
            current_lights = self._lights
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return True
            elif event.type == pygame.KEYUP:
                if self._is_quit_shortcut(event.key):
                    return True
                elif event.key == K_BACKSPACE:
                    if self._autopilot_enabled:
                        world.player.set_autopilot(False)
                        world.restart()
                        world.player.set_autopilot(True)
                    else:
                        world.restart()
                elif event.key == K_F1:
                    world.hud.toggle_info()
                elif event.key == K_v and pygame.key.get_mods() & KMOD_SHIFT:
                    world.next_map_layer(reverse=True)
                elif event.key == K_v:
                    world.next_map_layer()
                elif event.key == K_b and pygame.key.get_mods() & KMOD_SHIFT:
                    world.load_map_layer(unload=True)
                elif event.key == K_b:
                    world.load_map_layer()
                elif event.key == K_h or (event.key == K_SLASH and pygame.key.get_mods() & KMOD_SHIFT):
                    world.hud.help.toggle()
                elif event.key == K_TAB:
                    world.camera_manager.toggle_camera()
                elif event.key == K_c and pygame.key.get_mods() & KMOD_SHIFT:
                    world.next_weather(reverse=True)
                elif event.key == K_c:
                    world.next_weather()
                elif event.key == K_g:
                    world.toggle_radar()
                elif event.key == K_BACKQUOTE:
                    world.camera_manager.next_sensor()
                elif event.key == K_n:
                    world.camera_manager.next_sensor()
                elif event.key == K_w and (pygame.key.get_mods() & KMOD_CTRL):
                    if world.constant_velocity_enabled:
                        world.player.disable_constant_velocity()
                        world.constant_velocity_enabled = False
                        world.hud.notification("Disabled Constant Velocity Mode")
                    else:
                        world.player.enable_constant_velocity(carla.Vector3D(17, 0, 0))
                        world.constant_velocity_enabled = True
                        world.hud.notification("Enabled Constant Velocity Mode at 60 km/h")
                elif event.key == K_o:
                    try:
                        if world.doors_are_open:
                            world.hud.notification("Closing Doors")
                            world.doors_are_open = False
                            world.player.close_door(carla.VehicleDoor.All)
                        else:
                            world.hud.notification("Opening doors")
                            world.doors_are_open = True
                            world.player.open_door(carla.VehicleDoor.All)
                    except Exception:
                        pass
                elif event.key == K_t:
                    if world.show_vehicle_telemetry:
                        world.player.show_debug_telemetry(False)
                        world.show_vehicle_telemetry = False
                        world.hud.notification("Disabled Vehicle Telemetry")
                    else:
                        try:
                            world.player.show_debug_telemetry(True)
                            world.show_vehicle_telemetry = True
                            world.hud.notification("Enabled Vehicle Telemetry")
                        except Exception:
                            pass
                elif event.key > K_0 and event.key <= K_9:
                    index_ctrl = 0
                    if pygame.key.get_mods() & KMOD_CTRL:
                        index_ctrl = 9
                    world.camera_manager.set_sensor(event.key - 1 - K_0 + index_ctrl)
                elif event.key == K_r and not (pygame.key.get_mods() & KMOD_CTRL):
                    world.camera_manager.toggle_recording()
                elif event.key == K_r and (pygame.key.get_mods() & KMOD_CTRL):
                    if (world.recording_enabled):
                        client.stop_recorder()
                        world.recording_enabled = False
                        world.hud.notification("Recorder is OFF")
                    else:
                        client.start_recorder("manual_recording.rec")
                        world.recording_enabled = True
                        world.hud.notification("Recorder is ON")
                elif event.key == K_p and (pygame.key.get_mods() & KMOD_CTRL):
                    # stop recorder
                    client.stop_recorder()
                    world.recording_enabled = False
                    # work around to fix camera at start of replaying
                    current_index = world.camera_manager.index
                    world.destroy_sensors()
                    # disable autopilot
                    self._autopilot_enabled = False
                    world.player.set_autopilot(self._autopilot_enabled)
                    world.hud.notification("Replaying file 'manual_recording.rec'")
                    # replayer
                    client.replay_file("manual_recording.rec", world.recording_start, 0, 0)
                    world.camera_manager.set_sensor(current_index)
                elif event.key == K_MINUS and (pygame.key.get_mods() & KMOD_CTRL):
                    if pygame.key.get_mods() & KMOD_SHIFT:
                        world.recording_start -= 10
                    else:
                        world.recording_start -= 1
                    world.hud.notification("Recording start time is %d" % (world.recording_start))
                elif event.key == K_EQUALS and (pygame.key.get_mods() & KMOD_CTRL):
                    if pygame.key.get_mods() & KMOD_SHIFT:
                        world.recording_start += 10
                    else:
                        world.recording_start += 1
                    world.hud.notification("Recording start time is %d" % (world.recording_start))
                if isinstance(self._control, carla.VehicleControl):
                    if event.key == K_q:
                        self._control.gear = 1 if self._control.reverse else -1
                    elif event.key == K_m:
                        self._control.manual_gear_shift = not self._control.manual_gear_shift
                        self._control.gear = world.player.get_control().gear
                        world.hud.notification('%s Transmission' %
                                               ('Manual' if self._control.manual_gear_shift else 'Automatic'))
                    elif self._control.manual_gear_shift and event.key == K_COMMA:
                        self._control.gear = max(-1, self._control.gear - 1)
                    elif self._control.manual_gear_shift and event.key == K_PERIOD:
                        self._control.gear = self._control.gear + 1
                    elif event.key == K_p and not pygame.key.get_mods() & KMOD_CTRL:
                        if not self._autopilot_enabled and not sync_mode:
                            print("WARNING: You are currently in asynchronous mode and could "
                                  "experience some issues with the traffic simulation")
                        self._autopilot_enabled = not self._autopilot_enabled
                        world.player.set_autopilot(self._autopilot_enabled)
                        world.hud.notification(
                            'Autopilot %s' % ('On' if self._autopilot_enabled else 'Off'))
                    elif event.key == K_l and pygame.key.get_mods() & KMOD_CTRL:
                        current_lights ^= carla.VehicleLightState.Special1
                    elif event.key == K_l and pygame.key.get_mods() & KMOD_SHIFT:
                        current_lights ^= carla.VehicleLightState.HighBeam
                    elif event.key == K_l:
                        # Use 'L' key to switch between lights:
                        # closed -> position -> low beam -> fog
                        if not self._lights & carla.VehicleLightState.Position:
                            world.hud.notification("Position lights")
                            current_lights |= carla.VehicleLightState.Position
                        else:
                            world.hud.notification("Low beam lights")
                            current_lights |= carla.VehicleLightState.LowBeam
                        if self._lights & carla.VehicleLightState.LowBeam:
                            world.hud.notification("Fog lights")
                            current_lights |= carla.VehicleLightState.Fog
                        if self._lights & carla.VehicleLightState.Fog:
                            world.hud.notification("Lights off")
                            current_lights ^= carla.VehicleLightState.Position
                            current_lights ^= carla.VehicleLightState.LowBeam
                            current_lights ^= carla.VehicleLightState.Fog
                    elif event.key == K_i:
                        current_lights ^= carla.VehicleLightState.Interior
                    elif event.key == K_z:
                        current_lights ^= carla.VehicleLightState.LeftBlinker
                    elif event.key == K_x:
                        current_lights ^= carla.VehicleLightState.RightBlinker

        if not self._autopilot_enabled:
            if isinstance(self._control, carla.VehicleControl):
                self._parse_vehicle_keys(pygame.key.get_pressed(), clock.get_time())
                self._control.reverse = self._control.gear < 0
                # Set automatic control-related vehicle lights
                if self._control.brake:
                    current_lights |= carla.VehicleLightState.Brake
                else: # Remove the Brake flag
                    current_lights &= ~carla.VehicleLightState.Brake
                if self._control.reverse:
                    current_lights |= carla.VehicleLightState.Reverse
                else: # Remove the Reverse flag
                    current_lights &= ~carla.VehicleLightState.Reverse
                if current_lights != self._lights: # Change the light state only if necessary
                    self._lights = current_lights
                    world.player.set_light_state(carla.VehicleLightState(self._lights))
            elif isinstance(self._control, carla.WalkerControl):
                self._parse_walker_keys(pygame.key.get_pressed(), clock.get_time(), world)
            world.player.apply_control(self._control)

    def _parse_vehicle_keys(self, keys, milliseconds):
        if keys[K_UP] or keys[K_w]:
            self._control.throttle = min(self._control.throttle + 0.01, 1.00)
        else:
            self._control.throttle = 0.0

        if keys[K_DOWN] or keys[K_s]:
            self._control.brake = min(self._control.brake + 0.2, 1)
        else:
            self._control.brake = 0

        steer_increment = 5e-4 * milliseconds
        if keys[K_LEFT] or keys[K_a]:
            if self._steer_cache > 0:
                self._steer_cache = 0
            else:
                self._steer_cache -= steer_increment
        elif keys[K_RIGHT] or keys[K_d]:
            if self._steer_cache < 0:
                self._steer_cache = 0
            else:
                self._steer_cache += steer_increment
        else:
            self._steer_cache = 0.0
        self._steer_cache = min(0.7, max(-0.7, self._steer_cache))
        self._control.steer = round(self._steer_cache, 1)
        self._control.hand_brake = keys[K_SPACE]

    def _parse_walker_keys(self, keys, milliseconds, world):
        self._control.speed = 0.0
        if keys[K_DOWN] or keys[K_s]:
            self._control.speed = 0.0
        if keys[K_LEFT] or keys[K_a]:
            self._control.speed = .01
            self._rotation.yaw -= 0.08 * milliseconds
        if keys[K_RIGHT] or keys[K_d]:
            self._control.speed = .01
            self._rotation.yaw += 0.08 * milliseconds
        if keys[K_UP] or keys[K_w]:
            self._control.speed = world.player_max_speed_fast if pygame.key.get_mods() & KMOD_SHIFT else world.player_max_speed
        self._control.jump = keys[K_SPACE]
        self._rotation.yaw = round(self._rotation.yaw, 1)
        self._control.direction = self._rotation.get_forward_vector()

    @staticmethod
    def _is_quit_shortcut(key):
        return (key == K_ESCAPE) or (key == K_q and pygame.key.get_mods() & KMOD_CTRL)



# ==============================================================================
# -- HUD -----------------------------------------------------------------------
# ==============================================================================


class HUD(object):
    def __init__(self, width, height):
        self.dim = (width, height)
        font = pygame.font.Font(pygame.font.get_default_font(), 20)
        font_name = 'courier' if os.name == 'nt' else 'mono'
        fonts = [x for x in pygame.font.get_fonts() if font_name in x]
        default_font = 'ubuntumono'
        mono = default_font if default_font in fonts else fonts[0]
        mono = pygame.font.match_font(mono)
        self._font_mono = pygame.font.Font(mono, 12 if os.name == 'nt' else 14)
        #self._notifications = FadingText(font, (width, 40), (0, height - 40))
        #self.help = HelpText(pygame.font.Font(mono, 16), width, height)
        self.server_fps = 0
        self.frame = 0
        self.simulation_time = 0
        self._show_info = True
        self._info_text = []
        self._server_clock = pygame.time.Clock()

    def on_world_tick(self, timestamp):
        self._server_clock.tick()
        self.server_fps = self._server_clock.get_fps()
        self.frame = timestamp.frame
        self.simulation_time = timestamp.elapsed_seconds

    def tick(self, world, clock):
        #self._notifications.tick(world, clock)
        if not self._show_info:
            return
        t = world.player.get_transform()
        v = world.player.get_velocity()
        c = world.player.get_control()
        compass = world.imu_sensor.compass
        heading = 'N' if compass > 270.5 or compass < 89.5 else ''
        heading += 'S' if 90.5 < compass < 269.5 else ''
        heading += 'E' if 0.5 < compass < 179.5 else ''
        heading += 'W' if 180.5 < compass < 359.5 else ''
        colhist = world.collision_sensor.get_collision_history()
        collision = [colhist[x + self.frame - 200] for x in range(0, 200)]
        max_col = max(1.0, max(collision))
        collision = [x / max_col for x in collision]
        vehicles = world.world.get_actors().filter('vehicle.*')
        self._info_text = [
            'Server:  % 16.0f FPS' % self.server_fps,
            'Client:  % 16.0f FPS' % clock.get_fps(),
            '',
            'Vehicle: % 20s' % get_actor_display_name(world.player, truncate=20),
            'Map:     % 20s' % world.map.name.split('/')[-1],
            '',
            'Speed:   % 15.0f km/h' % (3.6 * math.sqrt(v.x**2 + v.y**2 + v.z**2)),
            u'Compass:% 17.0f\N{DEGREE SIGN} % 2s' % (compass, heading),
            'Accelero: (%5.1f,%5.1f,%5.1f)' % (world.imu_sensor.accelerometer),
            'Gyroscop: (%5.1f,%5.1f,%5.1f)' % (world.imu_sensor.gyroscope),
            'Location:% 20s' % ('(% 5.1f, % 5.1f)' % (t.location.x, t.location.y)),
            'GNSS:% 24s' % ('(% 2.6f, % 3.6f)' % (world.gnss_sensor.lat, world.gnss_sensor.lon)),
            'Height:  % 18.0f m' % t.location.z,
            '']
        if isinstance(c, carla.VehicleControl):
            self._info_text += [
                ('Throttle:', c.throttle, 0.0, 1.0),
                ('Steer:', c.steer, -1.0, 1.0),
                ('Brake:', c.brake, 0.0, 1.0),
                ('Reverse:', c.reverse),
                ('Hand brake:', c.hand_brake),
                ('Manual:', c.manual_gear_shift),
                'Gear:        %s' % {-1: 'R', 0: 'N'}.get(c.gear, c.gear)]
        elif isinstance(c, carla.WalkerControl):
            self._info_text += [
                ('Speed:', c.speed, 0.0, 5.556),
                ('Jump:', c.jump)]
        self._info_text += [
            '',
            'Collision:',
            collision,
            '',
            'Number of vehicles: % 8d' % len(vehicles)]
        if len(vehicles) > 1:
            self._info_text += ['Nearby vehicles:']
            distance = lambda l: math.sqrt((l.x - t.location.x)**2 + (l.y - t.location.y)**2 + (l.z - t.location.z)**2)
            vehicles = [(distance(x.get_location()), x) for x in vehicles if x.id != world.player.id]
            for d, vehicle in sorted(vehicles, key=lambda vehicles: vehicles[0]):
                if d > 200.0:
                    break
                vehicle_type = get_actor_display_name(vehicle, truncate=22)
                self._info_text.append('% 4dm %s' % (d, vehicle_type))

    def toggle_info(self):
        self._show_info = not self._show_info

    def notification(self, text, seconds=2.0):
        self._notifications.set_text(text, seconds=seconds)

    def error(self, text):
        self._notifications.set_text('Error: %s' % text, (255, 0, 0))




class DMCarlaClient():
    block_size = 150
    lane_width = 3.5

    bot_colors = []

#    bot_blueprint_names = ['vehicle.tesla.model3', 'vehicle.nissan.micra', 'vehicle.volkswagen.t2',
#                           'vehicle.mini.cooperst', 'vehicle.citroen.c3']
    bot_blueprint_names = ['vehicle.tesla.model3']

    bot_blueprint_colors = ['147,130,127', '107,162,146', '53,206,141', '188,216,183', '224,210,195',
                        '255,237,101', '180,173,234']

    def __init__(self):
        try:
            self.exp_info = self.get_exp_info()
            self.n_routes_per_session = 4

            self.set_ff_gain()
            self.initialize_log()
            self.client = carla.Client('localhost', 2000)
            self.client.set_timeout(2.0)
            pygame.init()
            self.world = self.client.get_world()

            self.tta_conditions = [4, 5, 6]
            self.bot_distance_values = [90, 120, 150]

            # x and y indices of the intersection
            # (0, 0) is the intersection in the bottom left corner of the map
            # (4, 4) is the intersection in the top right corner of the map
            self.origin = np.array([0.0, 0.0])

            # (1,0) is east, (-1,0) is west, (0,1) is north, (0,-1) is south
            self.active_intersection = np.array([1.0, 0.0])

            self.sound_cues = {(1, 1): 'next_turn_left',
                               (1, 0): 'next_go_straight',
                               (1, -1): 'next_turn_right',
                               (2, 1): 'turn_left',
                               (2, 0): 'go_straight',
                               (2, -1): 'turn_right'}

            self.ego_actor = None
            self.bot_actor = None
            self.bot_actor_blueprints = [random.choice(self.world.get_blueprint_library().filter(bp_name))
                                            for bp_name in self.bot_blueprint_names]

            self.empty_control = carla.VehicleControl(hand_brake=False, reverse=False, manual_gear_shift = False)
            self.control = self.empty_control

        except KeyboardInterrupt:
            for actor in self.world.get_actors():
                actor.destroy()

    def set_ff_gain(self, gain=35):
        ffset_cmd = 'ffset /dev/input/event%i -a %i'
        for i in range(5,10):
            os.system(ffset_cmd % (i, gain))

    def generate_tta_values(self):
        tta_values = []
        for tta in self.tta_conditions:
            # 5 is the number of left turns per route per tta
            tta_values = np.append(tta_values, np.ones(5)*tta)
        np.random.shuffle(tta_values)

        return tta_values

    def initialize_log(self):
        log_directory = 'C:/carla/carla/PythonAPI/examples/data'
        self.log_file_path = log_directory + '/' + str(self.exp_info['subj_id']) + '.txt'
        print(self.log_file_path)
        with open(self.log_file_path, 'w+') as fp:
            writer = csv.writer(fp, delimiter = '\t')
            writer.writerow(['subj_id', 't',
                             'ego_distance_to_end', 'ego_distance_to_bot', 'tta_condition', 'd_condition', 'v_condition',
                             'ego_x', 'ego_y', 'ego_vx', 'ego_vy', 'ego_ax', 'ego_ay', 'ego_yaw',
                             'bot_x', 'bot_y', 'bot_vx', 'bot_vy', 'bot_ax', 'bot_ay', 'bot_yaw',
                             'throttle', 'brake', 'steer', 'merge'])

    def write_log(self, log):
        with open(self.log_file_path, 'a') as fp:
            writer = csv.writer(fp, delimiter = '\t', )
            writer.writerows(log)

    def get_exp_info(self):
        root = tkr.Tk()
        app = ExpInfoUI(master=root)
        app.mainloop()
        exp_info = app.exp_info
        root.destroy()

        return exp_info

    def rotate(self, vector, angle):
        c, s = np.cos(angle), np.sin(angle)
        return np.squeeze(np.asarray(np.dot(np.matrix([[c, -s], [s, c]]), vector)))

    def update_ego_control(self):
        reverse = False
        K1 = 1.0  # 0.55
        steerCmd = K1 * math.tan(1.1)# * self.joystick.get_axis(0))

        K2 = 1.6  # 1.6
        throttleCmd = 1#K2 + (2.05 * math.log10(-0.7 * self.joystick.get_axis(2) + 1.4) - 1.2) / 0.92
        if throttleCmd <= 0:
            throttleCmd = 0
        elif throttleCmd > 1:
            throttleCmd = 1

        # cap the speed at 20 m/s
        speed = 20#np.sqrt(self.ego_actor.get_velocity().x**2 + self.ego_actor.get_velocity().y**2)
        if speed > 20:
            throttleCmd = 0

        brakeCmd = 0#1.6 + (2.05 * math.log10(-0.7 * self.joystick.get_axis(3) + 1.4) - 1.2) / 0.92
        if brakeCmd <= 0:
            brakeCmd = 0
        elif brakeCmd > 1:
            brakeCmd = 1

        #if self.joystick.get_button(5):
        #    reverse = True
        #elif self.joystick.get_button(4):
        #    reverse = False

        for event in pygame.event.get():
            if event.type == pygame.KEYUP:
                if event.key == pygame.locals.K_ESCAPE:
                    raise KeyboardInterrupt

        self.control.throttle = throttleCmd
        self.control.steer = steerCmd
        self.control.brake = brakeCmd
        self.control.reverse = reverse

        #self.ego_actor.apply_control(self.control) #check

    def spawn_ego_car(self):
        '''
        To shift the starting position from the center of the intersection to the lane where
        the driver can start driving towards the first active intersection, we rotate the
        heading direction 90` clockwise (-np.pi/2), and shift the origin towards that direction by half lane width
        '''
        start_position = self.origin*self.block_size + \
                        self.rotate(self.active_intersection-self.origin, -np.pi/2)*self.lane_width/2
        self.ego_start_position = self.world.get_map().get_waypoint(
            carla.Location(x=start_position[0], y=-start_position[1], z=0))

        self.ego_start_position = carla.Transform(carla.Location(x = -99, y = 137, z = 3), carla.Rotation(yaw = 225))  #spawn point ego vehicle on ramp Town04

        ego_bp = random.choice(self.world.get_blueprint_library().filter('prius'))

        self.ego_actor = self.world.try_spawn_actor(ego_bp, self.ego_start_position) #self.world.spawn_actor(ego_bp, self.ego_start_position.transform)
        self.ego_actor.set_autopilot(True)

    def spawn_bot(self):#, distance_to_intersection, speed):
        bot_bp = random.choice(self.bot_actor_blueprints)
        bot_bp.set_attribute('color', random.choice(self.bot_blueprint_colors))

        #ego_direction = self.active_intersection - self.origin

        #spawn_location = self.active_intersection*self.block_size + \
        #                    distance_to_intersection*(ego_direction) + \
        #                    (self.lane_width/2) * self.rotate(ego_direction, np.pi/2)
        #spawn_waypoint = self.world.get_map().get_waypoint(
        #                carla.Location(x=spawn_location[0], y=-spawn_location[1], z=0))

        spawn_point = carla.Transform(carla.Location(x = -175, y = 33.8, z = 11), carla.Rotation(yaw = 0.0))  #spawn point bot vehicle on highway Town04

        self.bot_actor = self.world.spawn_actor(bot_bp, spawn_point)
        self.bot_actor.set_autopilot(True)

        #self.bot_velocity = speed*self.rotate(ego_direction, np.pi).astype(int)
        #self.bot_actor.set_velocity(carla.Vector3D(self.bot_velocity[0], -self.bot_velocity[1], 0))

    def update_bot_control(self, max_speed):
        self.bot_actor.set_velocity(carla.Vector3D(self.bot_velocity[0], -self.bot_velocity[1], 0))

    def play_sound_cue(self, number, direction):
        sound_filename = '%s.wav' % (self.sound_cues[(number, direction)])
        file_path = os.path.join('sounds', sound_filename)
        sound = pygame.mixer.Sound(file_path)
        sound.set_volume(0.5)
        sound.play()

    def initialize_noise_sound(self):
        file_path = 'sounds/tesla_noise.wav'
        self.noise_sound = pygame.mixer.Sound(file_path)
        self.noise_sound.set_volume(0.1)
        self.noise_sound.play(loops=-1)

    def get_actor_state(self, actor):
        state = ([actor.get_transform().location.x, -actor.get_transform().location.y,
                 actor.get_velocity().x, -actor.get_velocity().y,
                 actor.get_acceleration().x, -actor.get_acceleration().y,
                 actor.get_transform().rotation.yaw]
                 if not (actor is None) else np.zeros(7).tolist())
        return list(['%.4f' % value for value in state])

    def update_log(self, log, values_to_log):
        log.append((values_to_log + \
                    self.get_actor_state(self.ego_actor) + \
                    self.get_actor_state(self.bot_actor) + \
                    list(['%.4f' % value for value in [self.control.throttle, self.control.brake, self.control.steer]])))

    def run(self, args):
        try:
            print(self.exp_info)
            first_route = self.exp_info['route']
            world = None

            client = carla.Client('127.0.0.1', 2000)
            client.set_timeout(20.0)
            sim_world = client.get_world()

            #inits and loads for audio signal
            pygame.mixer.init()
            pygame.mixer.music.load('audio_arrow.wav')

            #introduce gaze tracking lib and video stream
            track = Tracking()
            webcam = cv2.VideoCapture('obama.webm')

            #hud = HUD(1, 1)
            #world = World(sim_world, hud, args)


            for i in range(first_route, self.n_routes_per_session+1):
                tta_values = self.generate_tta_values()
                self.origin = np.array([0.0, 0.0])
                self.active_intersection = np.array([1.0, 0.0])

                #self.joystick = pygame.joystick.Joystick(0)
                #self.joystick.init()

                self.spawn_ego_car()
                time.sleep(5)
                self.spawn_bot()

                #self.initialize_noise_sound() #took off
                # in the first session, we go through routes 1 to 4, in the second session, routes 5 to 8
                route_number = i + (self.exp_info['session']-1)*self.n_routes_per_session
                # in the path input file, -1 is turn right, 1 is turn left, 0 is go straight
                route = np.loadtxt(os.path.join('routes', 'route_%i.txt' % (route_number)))
                tta = tta_values[-1]

                # distance to the center of the ego car
                d_condition = random.choice(self.bot_distance_values)
                bot_speed = d_condition/tta

                # whenever we exchange y-coordinates with Carla server, we invert the sign
                end_highway = carla.Location(x=20.0, y=0.0, z=0.0)
                trial_log = []
                trial_start_time = time.time()

                print ('TTA %f, bot speed %f, distance %f' %
                            (tta, bot_speed, d_condition))

                count = 0
                target_count = 10
                while count < target_count:
                    #GAZE###############################################################################
                    _, frame = webcam.read()
                    track.refresh(frame)
                    frame = track.annotated_frame()
                    label = ""

                    if track.mid_check() and track.mid_check_H():
                        label = "Road"
                    elif track.positive_x_check():
                        label = "Left mirror"
                    elif track.negative_x_check():
                        label = "Right mirror"
                    elif track.positive_y_check():
                        label = "Rear view mirror"
                    elif track.negative_y_check():
                        label = "Center stack"
                    else:
                        label = "Blinking or NaN"

                    print("LABEL: ", label)
                    ####################################################################################

                    ####################################################################################
                    tf = self.ego_actor.get_transform()
                    if tf.location.x > -60.0:
                        d_remain = 75.0 - tf.location.x
                    else:
                        d_remain = 150.0


                    if tf.location.y > 36.0:
                        merge = 0
                    else:
                        merge = 1
                    ####################################################################################
                    if self.ego_actor.get_location().x > 10:
                        self.ego_actor.set_autopilot(False)  #remove autopilot at begin of merge

                    t = time.time()-trial_start_time
                    speed = np.sqrt(self.ego_actor.get_velocity().x**2 + self.ego_actor.get_velocity().y**2)
                    ego_distance_to_end = self.ego_actor.get_location().distance(end_highway)  #distance to end of highway
                    ego_distance_to_bot = self.ego_actor.get_location().distance(self.bot_actor.get_location())
                    '''
                    'subj_id', 't', 'ego_distance_to_end', 'tta_condition', 'd_condition', 'v_condition'
                    '''
                    values_to_log = list(['%i' % value for value in
                                          [self.exp_info['subj_id']]]) \
                                  + list(['%.4f' % value for value in
                                          [t, ego_distance_to_end, ego_distance_to_bot, tta, d_condition, bot_speed]]) \
                                  + list(['%i' % value for value in
                                          [merge]])

                    self.update_log(trial_log, values_to_log)
                    self.write_log(trial_log)  #TODO remove later when repeat works
                    self.update_ego_control()

                    if not self.bot_actor is None:
                        self.update_bot_control(bot_speed)


                    #---------------------------------------------

                        '''
                        if tf.x > xx or tf.y > xx:
                            set autopilot = false
                        '''
                        '''
                        if tf.x > 20 or tf.y > 1000:
                            if (not (self.ego_actor is None)):
                                self.ego_actor.destroy()
                                self.ego_actor = None
                                print("spawning...")
                                self.spawn_ego_car()
                                self.bot_actor.destroy()
                                self.bot_actor = None
                                self.spawn_bot()
                                print("spawned!")
                                count += 1
                        '''


                    time.sleep(0.01)

                    self.write_log(trial_log)

                self.noise_sound.stop()

                if (not (self.ego_actor is None)):
                    self.ego_actor.destroy()
                    self.ego_actor = None
                if (not (self.bot_actor is None)):
                    self.bot_actor.destroy()
                    self.bot_actor = None
                self.joystick.quit()

                time.sleep(5.0)

        except KeyboardInterrupt:
            for actor in self.world.get_actors():
                actor.destroy()
            if world is not None:
                world.destroy()


def main():
    argparser = argparse.ArgumentParser(
        description='CARLA Manual Control Client')
    argparser.add_argument(
        '-v', '--verbose',
        action='store_true',
        dest='debug',
        help='print debug information')
    argparser.add_argument(
        '--host',
        metavar='H',
        default='127.0.0.1',
        help='IP of the host server (default: 127.0.0.1)')
    argparser.add_argument(
        '-p', '--port',
        metavar='P',
        default=2000,
        type=int,
        help='TCP port to listen to (default: 2000)')
    argparser.add_argument(
        '-a', '--autopilot',
        action='store_true',
        help='enable autopilot')
    argparser.add_argument(
        '--res',
        metavar='WIDTHxHEIGHT',
        default='1280x720',
        help='window resolution (default: 1280x720)')
    argparser.add_argument(
        '--filter',
        metavar='PATTERN',
        default='vehicle.*',
        help='actor filter (default: "vehicle.*")')
    argparser.add_argument(
        '--generation',
        metavar='G',
        default='2',
        help='restrict to certain actor generation (values: "1","2","All" - default: "2")')
    argparser.add_argument(
        '--rolename',
        metavar='NAME',
        default='hero',
        help='actor role name (default: "hero")')
    argparser.add_argument(
        '--gamma',
        default=2.2,
        type=float,
        help='Gamma correction of the camera (default: 2.2)')
    argparser.add_argument(
        '--sync',
        action='store_true',
        help='Activate synchronous mode execution')
    args = argparser.parse_args()

    dm_carla_client = DMCarlaClient()
    dm_carla_client.run(args)

if __name__ == '__main__':
    main()


