// End-to-end virtual SDL controller tests; exercise the same input path as hardware.
#include "../src/main.hpp"
#include "../src/hid/gamepad.hpp"
#include "managers/usereventmanager.hpp"
#include <SDL2/SDL.h>
#include <cmath>
#include <cstdio>
#include <stdexcept>

namespace {
int checks = 0;
void require(bool ok, const char *message) {
  ++checks;
  if (!ok) throw std::runtime_error(message);
}
int attach() {
  SDL_VirtualJoystickDesc descriptor{};
  descriptor.version = SDL_VIRTUAL_JOYSTICK_DESC_VERSION;
  descriptor.type = SDL_JOYSTICK_TYPE_GAMECONTROLLER;
  descriptor.naxes = SDL_CONTROLLER_AXIS_MAX;
  descriptor.nbuttons = SDL_CONTROLLER_BUTTON_MAX;
  descriptor.axis_mask = (1u << SDL_CONTROLLER_AXIS_MAX) - 1;
  descriptor.button_mask = (1u << SDL_CONTROLLER_BUTTON_MAX) - 1;
  descriptor.vendor_id = 0x045e;
  descriptor.product_id = 0x0b13;
  descriptor.name = "Football Training Xbox Series Virtual Test";
  return SDL_JoystickAttachVirtualEx(&descriptor);
}
void pump() {
  SDL_JoystickUpdate();
  SDL_Event event;
  while (SDL_PollEvent(&event)) UserEventManager::GetInstance().InputSDLEvent(event);
}
}

int RunControllerTests() {
  SDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, "1");
  SDL_Joystick *virtualPad = nullptr;
  int device = -1;
  try {
    require(SDL_Init(SDL_INIT_GAMECONTROLLER | SDL_INIT_EVENTS) == 0, "SDL controller init failed");
    EnvironmentManager testClock;
    UserEventManager eventManager;
    int first = attach();
    require(first >= 0, "First virtual device attach failed");
    require(SDL_JoystickDetachVirtual(first) == 0, "First detach failed");
    pump();
    device = attach();
    require(device >= 0, "Virtual device attach failed");
    virtualPad = SDL_JoystickOpen(device);
    require(virtualPad != nullptr, "Virtual device open failed");
    require(SDL_JoystickInstanceID(virtualPad) > 0, "Test must use a nonzero SDL instance ID");
    pump();
    auto &events = UserEventManager::GetInstance();
    require(events.IsJoystickConnected(0), "Connected device not mapped to stable slot 0");
    require(events.IsGameController(0), "Virtual controller has no standard SDL mapping");
    HIDGamepad pad(0);
    pad.Process();
    require(!pad.GetButton(e_ButtonFunction_Dribble), "Released RT must not activate close control");
    require(!pad.GetButton(e_ButtonFunction_Special), "Released LT must not activate special");
    SDL_JoystickSetVirtualAxis(virtualPad, SDL_CONTROLLER_AXIS_LEFTX, 24000);
    SDL_JoystickSetVirtualAxis(virtualPad, SDL_CONTROLLER_AXIS_LEFTY, 0);
    pump();
    pad.Process();
    require(pad.GetDirection().coords[0] > 0.5f, "Analog movement missing or reversed");
    require(std::fabs(pad.GetDirection().coords[1]) < 0.01f, "Analog neutral Y drift");
    SDL_JoystickSetVirtualAxis(virtualPad, SDL_CONTROLLER_AXIS_LEFTX, 1000);
    pump(); pad.Process();
    require(pad.GetDirection().GetLength() == 0, "Deadzone does not remove analog drift");
    SDL_JoystickSetVirtualAxis(virtualPad, SDL_CONTROLLER_AXIS_TRIGGERRIGHT, 24000);
    pump(); pad.Process();
    require(pad.GetButton(e_ButtonFunction_Dribble), "RT not mapped to close control");
    SDL_JoystickSetVirtualButton(virtualPad, SDL_CONTROLLER_BUTTON_X, 1);
    pump(); pad.Process();
    require(pad.GetButton(e_ButtonFunction_Shot), "X not mapped to shot");
    require(!pad.GetPreviousButtonState(e_ButtonFunction_Shot), "Shot rising edge lost");
    pad.Process();
    require(pad.GetPreviousButtonState(e_ButtonFunction_Shot), "Previous input state not retained");
    SDL_Event invalid{};
    invalid.type = SDL_JOYAXISMOTION;
    invalid.jaxis.which = 987654;
    invalid.jaxis.axis = 255;
    events.InputSDLEvent(invalid);
    require(events.GetJoystickAxis(99, 99) == 0, "Out-of-bounds input must be rejected");
    SDL_Event blur{};
    blur.type = SDL_WINDOWEVENT;
    blur.window.event = SDL_WINDOWEVENT_FOCUS_LOST;
    events.InputSDLEvent(blur);
    pad.Process();
    require(!pad.GetButton(e_ButtonFunction_Shot), "Button stuck after focus loss");
    SDL_Event shortcut{};
    shortcut.type = SDL_KEYDOWN;
    shortcut.key.keysym.sym = SDLK_r;
    events.InputSDLEvent(shortcut);
    shortcut.type = SDL_KEYUP;
    events.InputSDLEvent(shortcut);
    require(!events.GetKeyboardState(SDLK_r), "Shortcut release state is incorrect");
    require(events.ConsumeKeyPress(SDLK_r), "Brief shortcut lost when keydown and keyup arrive together");
    require(!events.ConsumeKeyPress(SDLK_r), "Shortcut executes more than once");
    SDL_JoystickClose(virtualPad); virtualPad = nullptr;
    require(SDL_JoystickDetachVirtual(device) == 0, "Detach failed"); device = -1;
    pump(); pad.Process();
    require(!events.IsJoystickConnected(0), "Disconnected slot stayed connected");
    require(pad.GetDirection().GetLength() == 0, "Disconnected stick did not clear");
    device = attach();
    require(device >= 0, "Reconnect failed");
    pump();
    require(events.IsJoystickConnected(0), "Reconnect did not reuse stable slot");
    require(SDL_JoystickDetachVirtual(device) == 0, "Final detach failed"); device = -1;
    pump();
    printf("Controller tests: %d checks passed\n", checks);
    UserEventManager::GetInstance().Exit();
    SDL_Quit();
    return 0;
  } catch (const std::exception &error) {
    fprintf(stderr, "Controller test failed after %d checks: %s (SDL: %s)\n", checks, error.what(), SDL_GetError());
    if (virtualPad) SDL_JoystickClose(virtualPad);
    if (device >= 0) SDL_JoystickDetachVirtual(device);
    SDL_Quit();
    return 1;
  }
}
