// Copyright 2019 Google LLC & Bastiaan Konings
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// written by bastiaan konings schuiling 2008 - 2014
// this work is public domain. the code is undocumented, scruffy, untested, and should generally not be used for anything important.
// i do not offer support, so don't ask. to be used for inspiration :)

// Football Training: robust hotplug, focus loss and bounds-safe SDL2 input.
#include "usereventmanager.hpp"
#include <algorithm>

#include "environmentmanager.hpp"
#include "base/log.hpp"
#include "base/utils.hpp"

namespace blunted {

  template<> UserEventManager* Singleton<UserEventManager>::singleton = 0;

  UserEventManager::UserEventManager() {
    lastKeyTime_ms = 0;

    //SDL_EnableKeyRepeat(0, SDL_DEFAULT_REPEAT_INTERVAL);

    // yes, SDL starts mousebuttons at 1...
    for (int i = 1; i < 8; i++) {
      mousePressed[i] = false;
    }

    for (int j = 0; j < _JOYSTICK_MAX; j++) {
      joystick[j] = nullptr;
      for (int i = 0; i < _JOYSTICK_MAXBUTTONS; i++) {
        joyButtonPressed[j][i] = false;
      }
    }

    for (int j = 0; j < _JOYSTICK_MAX; j++) {
      for (int i = 0; i < _JOYSTICK_MAXAXES; i++) {
        joyAxis[j][i] = 0.0;
        joyAxisCalibration[j][i][0] = -32768.0;
        joyAxisCalibration[j][i][1] = 32767.0;
        joyAxisCalibration[j][i][2] = 0.0;
      }
    }


    // Initialize both SDL joystick layers.  Xbox Series controllers can be
    // exposed by Windows through XInput, HIDAPI, or Bluetooth; explicitly
    // enabling all three paths prevents a connected pad from being visible to
    // Windows but absent from SDL's controller list.
#ifdef _WIN32
    SDL_SetHint(SDL_HINT_XINPUT_ENABLED, "1");
    SDL_SetHint(SDL_HINT_JOYSTICK_HIDAPI, "1");
    SDL_SetHint(SDL_HINT_JOYSTICK_HIDAPI_XBOX, "1");
    SDL_SetHint(SDL_HINT_JOYSTICK_HIDAPI_XBOX_ONE, "1");
#endif
    SDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, "1");
    SDL_InitSubSystem(SDL_INIT_JOYSTICK | SDL_INIT_GAMECONTROLLER);
    SDL_GameControllerEventState(SDL_ENABLE);
    Log(e_Notice, "UserEventManager", "UserEventManager", "SDL joystick count: " + int_to_str(SDL_NumJoysticks()));
    for (int i = 0; i < SDL_NumJoysticks(); i++) {
      const char *name = SDL_JoystickNameForIndex(i);
      Log(e_Notice, "UserEventManager", "UserEventManager",
          "SDL device #" + int_to_str(i) + ": " + (name ? name : "unnamed") +
          (SDL_IsGameController(i) ? " (GameController)" : " (raw joystick)"));
      OpenJoystick(i);
    }
    //SDL_JoystickEventState(SDL_IGNORE); // doesn't seem to work? bug?
    SDL_JoystickEventState(SDL_ENABLE);
    //printf("JOYSTICK EVENT STATE: %i (%i = ignore, %i = enable)\n", SDL_JoystickEventState(SDL_QUERY), SDL_IGNORE, SDL_ENABLE);
  }

  UserEventManager::~UserEventManager() {
    Exit();
  }

  void UserEventManager::Exit() {
    for (int i = 0; i < _JOYSTICK_MAX; ++i) {
      if (gameController[i]) SDL_GameControllerClose(gameController[i]);
      else if (joystick[i]) SDL_JoystickClose(joystick[i]);
      joystick[i] = nullptr;
      gameController[i] = nullptr;
    }
  }

  int UserEventManager::FindJoystickSlot(SDL_JoystickID instance) const {
    for (int i = 0; i < _JOYSTICK_MAX; ++i)
      if (joystick[i] && SDL_JoystickInstanceID(joystick[i]) == instance) return i;
    return -1;
  }

  void UserEventManager::OpenJoystick(int deviceIndex) {
    if (deviceIndex < 0 || deviceIndex >= SDL_NumJoysticks()) return;
    if (FindJoystickSlot(SDL_JoystickGetDeviceInstanceID(deviceIndex)) >= 0) return;
    for (int slot = 0; slot < _JOYSTICK_MAX; ++slot) {
      if (!joystick[slot]) {
        if (SDL_IsGameController(deviceIndex)) {
          gameController[slot] = SDL_GameControllerOpen(deviceIndex);
          if (gameController[slot]) joystick[slot] = SDL_GameControllerGetJoystick(gameController[slot]);
        } else {
          joystick[slot] = SDL_JoystickOpen(deviceIndex);
        }
        if (!joystick[slot]) {
          Log(e_Warning, "UserEventManager", "OpenJoystick",
              "Could not open SDL device #" + int_to_str(deviceIndex) + ": " + SDL_GetError());
        } else {
          controllerInputsCleared[slot] = false;
          const char *name = SDL_JoystickName(joystick[slot]);
          Log(e_Notice, "UserEventManager", "OpenJoystick",
              "Opened controller slot " + int_to_str(slot) + ": " + (name ? name : "unnamed"));
        }
        return;
      }
    }
  }

  void UserEventManager::ClearInputs() {
    { boost::mutex::scoped_lock lock(keyPressedMutex); keyPressed.clear(); pendingKeyPresses.clear(); }
    { boost::mutex::scoped_lock lock(mousePressedMutex); std::fill(mousePressed, mousePressed + 8, false); }
    boost::mutex::scoped_lock lock(joyButtonPressedMutex);
    for (int slot = 0; slot < _JOYSTICK_MAX; ++slot) {
      std::fill(joyButtonPressed[slot], joyButtonPressed[slot] + _JOYSTICK_MAXBUTTONS, false);
      std::fill(joyAxis[slot], joyAxis[slot] + _JOYSTICK_MAXAXES, 0.0f);
      std::fill(controllerButtons[slot], controllerButtons[slot] + SDL_CONTROLLER_BUTTON_MAX, false);
      std::fill(controllerAxes[slot], controllerAxes[slot] + SDL_CONTROLLER_AXIS_MAX, 0.0f);
      controllerInputsCleared[slot] = true;
    }
  }

  void UserEventManager::InputSDLEvent(const SDL_Event &event) {
    int joyID = -1;
    switch (event.type) {
      case SDL_WINDOWEVENT:
        if (event.window.event == SDL_WINDOWEVENT_FOCUS_LOST) ClearInputs();
        break;
      case SDL_JOYDEVICEADDED:
      case SDL_CONTROLLERDEVICEADDED: {
        boost::mutex::scoped_lock lock(joyButtonPressedMutex);
        OpenJoystick(event.jdevice.which);
        break;
      }
      case SDL_JOYDEVICEREMOVED:
      case SDL_CONTROLLERDEVICEREMOVED: {
        boost::mutex::scoped_lock lock(joyButtonPressedMutex);
        int slot = FindJoystickSlot(event.jdevice.which);
        if (slot >= 0) {
          if (gameController[slot]) SDL_GameControllerClose(gameController[slot]);
          else SDL_JoystickClose(joystick[slot]);
          joystick[slot] = nullptr;
          gameController[slot] = nullptr;
          std::fill(joyButtonPressed[slot], joyButtonPressed[slot] + _JOYSTICK_MAXBUTTONS, false);
          std::fill(joyAxis[slot], joyAxis[slot] + _JOYSTICK_MAXAXES, 0.0f);
          std::fill(controllerButtons[slot], controllerButtons[slot] + SDL_CONTROLLER_BUTTON_MAX, false);
          std::fill(controllerAxes[slot], controllerAxes[slot] + SDL_CONTROLLER_AXIS_MAX, 0.0f);
          controllerInputsCleared[slot] = true;
        }
        break;
      }
      case SDL_CONTROLLERBUTTONDOWN:
      case SDL_CONTROLLERBUTTONUP: {
        boost::mutex::scoped_lock lock(joyButtonPressedMutex);
        int slot = FindJoystickSlot(event.cbutton.which);
        if (slot >= 0 && event.cbutton.button < SDL_CONTROLLER_BUTTON_MAX)
          controllerInputsCleared[slot] = false;
        if (slot >= 0 && event.cbutton.button < SDL_CONTROLLER_BUTTON_MAX)
          controllerButtons[slot][event.cbutton.button] = event.type == SDL_CONTROLLERBUTTONDOWN;
        break;
      }
      case SDL_CONTROLLERAXISMOTION: {
        boost::mutex::scoped_lock lock(joyButtonPressedMutex);
        int slot = FindJoystickSlot(event.caxis.which);
        if (slot >= 0 && event.caxis.axis < SDL_CONTROLLER_AXIS_MAX)
          controllerInputsCleared[slot] = false;
        if (slot >= 0 && event.caxis.axis < SDL_CONTROLLER_AXIS_MAX)
          controllerAxes[slot][event.caxis.axis] = event.caxis.value / (event.caxis.value < 0 ? 32768.0f : 32767.0f);
        break;
      }
      case SDL_KEYDOWN:
        keyPressedMutex.lock();
        keyPressed[event.key.keysym.sym].pressTime_ms = EnvironmentManager::GetInstance().GetTime_ms();
        if (!event.key.repeat) pendingKeyPresses.insert(event.key.keysym.sym);
        lastKeyTime_ms = keyPressed[event.key.keysym.sym].pressTime_ms;
        keyPressedMutex.unlock();
        break;
      case SDL_KEYUP:
        keyPressedMutex.lock();
        keyPressed.erase(event.key.keysym.sym);
        keyPressedMutex.unlock();
        break;
      case SDL_MOUSEBUTTONDOWN:
        if (event.button.button >= 8) break;
        mousePressedMutex.lock();
        mousePressed[event.button.button] = true;
        mousePressedMutex.unlock();
        break;
      case SDL_MOUSEBUTTONUP:
        if (event.button.button >= 8) break;
        mousePressedMutex.lock();
        mousePressed[event.button.button] = false;
        mousePressedMutex.unlock();
        break;
      case SDL_JOYAXISMOTION:
        joyButtonPressedMutex.lock();
        joyID = FindJoystickSlot(event.jaxis.which);
        if (joyID >= 0 && event.jaxis.axis < _JOYSTICK_MAXAXES) {
          controllerInputsCleared[joyID] = false;
          joyAxis[joyID][event.jaxis.axis] = event.jaxis.value;
        }
        joyButtonPressedMutex.unlock();
        break;
      case SDL_JOYBUTTONDOWN:
        joyButtonPressedMutex.lock();
        joyID = FindJoystickSlot(event.jbutton.which);
        if (joyID >= 0 && event.jbutton.button < _JOYSTICK_MAXBUTTONS) {
          controllerInputsCleared[joyID] = false;
          joyButtonPressed[joyID][event.jbutton.button] = true;
        }
        joyButtonPressedMutex.unlock();
        break;
      case SDL_JOYBUTTONUP:
        joyButtonPressedMutex.lock();
        joyID = FindJoystickSlot(event.jbutton.which);
        if (joyID >= 0 && event.jbutton.button < _JOYSTICK_MAXBUTTONS) {
          controllerInputsCleared[joyID] = false;
          joyButtonPressed[joyID][event.jbutton.button] = false;
        }
        joyButtonPressedMutex.unlock();
        break;
    }
  }

  bool UserEventManager::GetKeyboardState(SDL_Keycode code) const {
    boost::mutex::scoped_lock lock(keyPressedMutex);
    return keyPressed.count(code) > 0;
  }

  std::map<SDL_Keycode, TimedKeyPress> UserEventManager::GetKeyboardState() const {
    boost::mutex::scoped_lock lock(keyPressedMutex);
    return keyPressed;
  }

  bool UserEventManager::ConsumeKeyPress(SDL_Keycode key) {
    boost::mutex::scoped_lock lock(keyPressedMutex);
    return pendingKeyPresses.erase(key) > 0;
  }

  void UserEventManager::SetKeyboardState(SDL_Keycode key, bool newState) {
      boost::mutex::scoped_lock lock(keyPressedMutex);
      if (!newState) {
          keyPressed.erase(key);
      } else {
          keyPressed[key].pressTime_ms = EnvironmentManager::GetInstance().GetTime_ms();
      }
  }

  unsigned long UserEventManager::GetLastKeyPressDiff_ms() {
    boost::mutex::scoped_lock lock(keyPressedMutex);
    return EnvironmentManager::GetInstance().GetTime_ms() - lastKeyTime_ms;
  }

  unsigned long UserEventManager::GetLastKeyPressDiff_ms(SDL_Keycode key) {
    boost::mutex::scoped_lock lock(keyPressedMutex);
    return EnvironmentManager::GetInstance().GetTime_ms() - keyPressed[key].pressTime_ms;
  }

  bool UserEventManager::GetMouseButtonState(int sdlButtonID) const {
    boost::mutex::scoped_lock lock(mousePressedMutex);
    return mousePressed[sdlButtonID];
  }

  Vector3 UserEventManager::GetMouseRelativePos() const {
    Vector3 mousePos;
    mousePos.coords[2] = 0;
    int x, y;
    SDL_GetRelativeMouseState(&x, &y);
    mousePos.coords[0] = x;
    mousePos.coords[1] = y;
    return mousePos;
  }


  bool UserEventManager::GetJoyButtonState(int joyID, int sdlJoyButtonID) const {
    boost::mutex::scoped_lock lock(joyButtonPressedMutex);
    if (joyID < 0 || joyID >= _JOYSTICK_MAX || sdlJoyButtonID < 0 || sdlJoyButtonID >= _JOYSTICK_MAXBUTTONS) return false;
    if (!controllerInputsCleared[joyID] && joystick[joyID] && SDL_JoystickGetAttached(joystick[joyID]))
      return SDL_JoystickGetButton(joystick[joyID], sdlJoyButtonID) != 0;
    return joyButtonPressed[joyID][sdlJoyButtonID];
  }

  void UserEventManager::SetJoyButtonState(int joyID, int sdlJoyButtonID, bool newState) {
    boost::mutex::scoped_lock lock(joyButtonPressedMutex);
    if (joyID < 0 || joyID >= _JOYSTICK_MAX || sdlJoyButtonID < 0 || sdlJoyButtonID >= _JOYSTICK_MAXBUTTONS) return;
    joyButtonPressed[joyID][sdlJoyButtonID] = newState;
  }

  float UserEventManager::GetJoystickAxis(int joyID, int axisID, bool deadzone) const {
    boost::mutex::scoped_lock lock(joyButtonPressedMutex);
    if (joyID < 0 || joyID >= _JOYSTICK_MAX || axisID < 0 || axisID >= _JOYSTICK_MAXAXES) return 0.0f;

    float min = joyAxisCalibration[joyID][axisID][0];
    float max = joyAxisCalibration[joyID][axisID][1];
    float rest = joyAxisCalibration[joyID][axisID][2];

    float value = joyAxis[joyID][axisID];
    if (!controllerInputsCleared[joyID] && joystick[joyID] && SDL_JoystickGetAttached(joystick[joyID]) &&
        axisID < SDL_JoystickNumAxes(joystick[joyID])) {
      value = SDL_JoystickGetAxis(joystick[joyID], axisID);
    }

    if (value < min) value = min;
    if (value > max) value = max;
    float scale = max - min;
    if (scale == 0.0) scale = 0.01; // avoid division by zero, axis would be defunct though if scale evaluates to 0

    // bring value in range 0 .. 1
    value -= min;
    value /= scale;

    // bring rest in range 0 .. 1
    rest -= min;
    rest /= scale;

    // deadzone
    if (deadzone)
      if (fabs(rest - value) < 0.1) value = rest;

    if (value < rest) {
      // bring value in range 0 .. -1
      value /= rest;
      value -= 1.0;
    } else if (value > rest) {
      // bring value in range 0 .. 1
      scale = 1.0 - rest;
      value -= rest;
      value /= scale;
    } else { // value == rest
      value = 0.0;
    }

    return value;
  }

  float UserEventManager::GetJoystickAxisRaw(int joyID, int axisID) const {
    boost::mutex::scoped_lock lock(joyButtonPressedMutex);
    if (joyID < 0 || joyID >= _JOYSTICK_MAX || axisID < 0 || axisID >= _JOYSTICK_MAXAXES) return 0.0f;
    if (!controllerInputsCleared[joyID] && joystick[joyID] && SDL_JoystickGetAttached(joystick[joyID]) &&
        axisID < SDL_JoystickNumAxes(joystick[joyID]))
      return SDL_JoystickGetAxis(joystick[joyID], axisID);
    return joyAxis[joyID][axisID];
  }

  bool UserEventManager::GetJoystickButton(int joyID, int buttonID) const {
    boost::mutex::scoped_lock lock(joyButtonPressedMutex);
    if (joyID < 0 || joyID >= _JOYSTICK_MAX || buttonID < 0 || buttonID >= _JOYSTICK_MAXBUTTONS) return false;
    if (!controllerInputsCleared[joyID] && joystick[joyID] && SDL_JoystickGetAttached(joystick[joyID]) &&
        buttonID < SDL_JoystickNumButtons(joystick[joyID]))
      return SDL_JoystickGetButton(joystick[joyID], buttonID) != 0;
    return joyButtonPressed[joyID][buttonID];
  }

  bool UserEventManager::IsJoystickConnected(int slot) const {
    boost::mutex::scoped_lock lock(joyButtonPressedMutex);
    return slot >= 0 && slot < _JOYSTICK_MAX && joystick[slot] && SDL_JoystickGetAttached(joystick[slot]);
  }
  bool UserEventManager::IsGameController(int slot) const {
    boost::mutex::scoped_lock lock(joyButtonPressedMutex);
    return slot >= 0 && slot < _JOYSTICK_MAX && gameController[slot] && SDL_GameControllerGetAttached(gameController[slot]);
  }
  bool UserEventManager::GetControllerButton(int slot, SDL_GameControllerButton button) const {
    boost::mutex::scoped_lock lock(joyButtonPressedMutex);
    if (slot < 0 || slot >= _JOYSTICK_MAX || button < 0 || button >= SDL_CONTROLLER_BUTTON_MAX) return false;
    if (!controllerInputsCleared[slot] && gameController[slot] && SDL_GameControllerGetAttached(gameController[slot]))
      return SDL_GameControllerGetButton(gameController[slot], button) != 0;
    return controllerButtons[slot][button];
  }
  float UserEventManager::GetControllerAxis(int slot, SDL_GameControllerAxis axis) const {
    boost::mutex::scoped_lock lock(joyButtonPressedMutex);
    if (slot < 0 || slot >= _JOYSTICK_MAX || axis < 0 || axis >= SDL_CONTROLLER_AXIS_MAX) return 0.0f;
    if (!controllerInputsCleared[slot] && gameController[slot] && SDL_GameControllerGetAttached(gameController[slot])) {
      const Sint16 value = SDL_GameControllerGetAxis(gameController[slot], axis);
      return value / (value < 0 ? 32768.0f : 32767.0f);
    }
    return controllerAxes[slot][axis];
  }

  float UserEventManager::GetJoystickAxisCalibrationMin(int joyID, int axisID) {
    boost::mutex::scoped_lock lock(joyButtonPressedMutex);
    return joyAxisCalibration[joyID][axisID][0];
  }

  float UserEventManager::GetJoystickAxisCalibrationMax(int joyID, int axisID) {
    boost::mutex::scoped_lock lock(joyButtonPressedMutex);
    return joyAxisCalibration[joyID][axisID][1];
  }

  float UserEventManager::GetJoystickAxisCalibrationRest(int joyID, int axisID) {
    boost::mutex::scoped_lock lock(joyButtonPressedMutex);
    return joyAxisCalibration[joyID][axisID][2];
  }

  void UserEventManager::SetJoystickAxisCalibration(int joyID, int axisID, float min, float max, float rest) {
    boost::mutex::scoped_lock lock(joyButtonPressedMutex);
    joyAxisCalibration[joyID][axisID][0] = min;
    joyAxisCalibration[joyID][axisID][1] = max;
    joyAxisCalibration[joyID][axisID][2] = rest;

    // rest has to be within min/max range
    if (joyAxisCalibration[joyID][axisID][2] < joyAxisCalibration[joyID][axisID][0]) joyAxisCalibration[joyID][axisID][2] = joyAxisCalibration[joyID][axisID][0];
    if (joyAxisCalibration[joyID][axisID][2] > joyAxisCalibration[joyID][axisID][1]) joyAxisCalibration[joyID][axisID][2] = joyAxisCalibration[joyID][axisID][1];
    joyAxis[joyID][axisID] = rest;
  }

}
