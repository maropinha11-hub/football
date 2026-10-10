// written by bastiaan konings schuiling 2008 - 2014
// this work is public domain. the code is undocumented, scruffy, untested, and should generally not be used for anything important.
// i do not offer support, so don't ask. to be used for inspiration :)

#include "environmentmanager.hpp"

#include <SDL2/SDL.h>
#include <boost/thread.hpp>

namespace blunted {

  template<> EnvironmentManager* Singleton<EnvironmentManager>::singleton = 0;

  EnvironmentManager::EnvironmentManager() {
    quit.SetData(false);
    startCounter = SDL_GetPerformanceCounter();
    counterFrequency = SDL_GetPerformanceFrequency();
  };

  EnvironmentManager::~EnvironmentManager() {
  };

  unsigned long EnvironmentManager::GetTime_ms() {
    const Uint64 elapsed = SDL_GetPerformanceCounter() - startCounter;
    return static_cast<unsigned long>((elapsed / counterFrequency) * 1000 +
        (elapsed % counterFrequency) * 1000 / counterFrequency);
  }

  void EnvironmentManager::Pause_ms(int duration) {
    boost::this_thread::sleep(boost::posix_time::milliseconds(duration));
  }

  void EnvironmentManager::SignalQuit() {
    quit.SetData(true);
  }

  bool EnvironmentManager::GetQuit() {
    return quit.GetData();
  }

}
