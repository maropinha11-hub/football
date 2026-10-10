// written by bastiaan konings schuiling 2008 - 2014
// this work is public domain. the code is undocumented, scruffy, untested, and should generally not be used for anything important.
// i do not offer support, so don't ask. to be used for inspiration :)

#include "command.hpp"

namespace blunted {

  Command::Command(const std::string &name) : handled(false) {
    this->name.SetData(name);
  }

  Command::~Command() {
  }

  bool Command::IsReady() {
    boost::mutex::scoped_lock lock(mutex);
    return handled;
  }

  void Command::Reset() {
    boost::mutex::scoped_lock lock(mutex);
    handled = false;
  }

  bool Command::Handle(void *caller) {
    bool result = Execute(caller);

    {
      boost::mutex::scoped_lock lock(mutex);
      handled = true;
      processed.notify_one();
    }
    // Publish readiness before waking the scheduler. Release this mutex
    // first: the scheduler holds its own mutex while checking IsReady().
    OnComplete();

    return result;
  }

  void Command::Wait() {
    boost::mutex::scoped_lock lock(mutex);
    if (!handled) {
      processed.wait(lock);
    }
  }

}
