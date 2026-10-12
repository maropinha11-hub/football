// Linux test preload: a real SDL virtual Xbox pad inside the game process.
// Axes/buttons come from a local test control file; the shipped game has no
// injection path. This exercises the same SDL/HID code as a physical pad.
#include <SDL2/SDL.h>
#include <dlfcn.h>
#include <cstdio>
#include <cstdlib>

namespace {
SDL_Joystick* pad=nullptr;
bool attaching=false;
const char* control() { return std::getenv("FOOTBALL_TEST_PAD_FILE"); }
}
extern "C" int SDL_NumJoysticks() {
  static auto real=reinterpret_cast<int(*)()>(dlsym(RTLD_NEXT,"SDL_NumJoysticks"));
  if(!pad&&!attaching&&control()&&(SDL_WasInit(SDL_INIT_JOYSTICK)&SDL_INIT_JOYSTICK)) {
    attaching=true;
    SDL_VirtualJoystickDesc desc{};desc.version=SDL_VIRTUAL_JOYSTICK_DESC_VERSION;
    desc.type=SDL_JOYSTICK_TYPE_GAMECONTROLLER;desc.naxes=SDL_CONTROLLER_AXIS_MAX;
    desc.nbuttons=SDL_CONTROLLER_BUTTON_MAX;
    desc.axis_mask=(1u<<SDL_CONTROLLER_AXIS_MAX)-1;desc.button_mask=(1u<<SDL_CONTROLLER_BUTTON_MAX)-1;
    desc.vendor_id=0x045e;desc.product_id=0x0b13;desc.name="Native training Xbox Series regression pad";
    const int index=SDL_JoystickAttachVirtualEx(&desc);
    if(index>=0)pad=SDL_JoystickOpen(index);
    attaching=false;
  }
  return real();
}
extern "C" void SDL_JoystickUpdate() {
  static auto real=reinterpret_cast<void(*)()>(dlsym(RTLD_NEXT,"SDL_JoystickUpdate"));
  if(pad&&control()) {
    int axes[6]={0,0,0,0,-32768,-32768};unsigned buttons=0;
    if(FILE* file=std::fopen(control(),"r")) {
      if(std::fscanf(file,"%d %d %d %d %d %d %u",&axes[0],&axes[1],&axes[2],&axes[3],&axes[4],&axes[5],&buttons)==7) {
        for(unsigned i=0;i<6;++i)SDL_JoystickSetVirtualAxis(pad,i,Sint16(axes[i]));
        for(unsigned i=0;i<SDL_CONTROLLER_BUTTON_MAX;++i)SDL_JoystickSetVirtualButton(pad,i,(buttons>>i)&1u);
      }
      std::fclose(file);
    }
  }
  real();
}
