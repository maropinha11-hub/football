// written by bastiaan konings schuiling 2008 - 2014
// this work is public domain. the code is undocumented, scruffy, untested, and should generally not be used for anything important.
// i do not offer support, so don't ask. to be used for inspiration :)

#include "iusertask.hpp"

#include "framework/scheduler.hpp"
#include "blunted.hpp"

namespace blunted {

  void IUserTaskMessage::OnComplete() {
    boost::mutex::scoped_lock lock(GetScheduler()->somethingIsDoneMutex);
    GetScheduler()->somethingIsDone.notify_one();
  }


  bool UserTaskMessage_GetPhase::Execute(void *caller) {
    task->GetPhase();
    return true;
  }

  bool UserTaskMessage_ProcessPhase::Execute(void *caller) {
    task->ProcessPhase();
    return true;
  }

  bool UserTaskMessage_PutPhase::Execute(void *caller) {
    task->PutPhase();
    return true;
  }

}
