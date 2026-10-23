// written by bastiaan konings schuiling 2008 - 2015
// this work is public domain. the code is undocumented, scruffy, untested, and should generally not be used for anything important.
// i do not offer support, so don't ask. to be used for inspiration :)

#ifndef _HPP_HUMANOIDBASE
#define _HPP_HUMANOIDBASE
#include <memory>

#include "base/math/vector3.hpp"
#include "scene/scene3d/node.hpp"

#include "../../../gamedefines.hpp"
#include "../../../utils.hpp"

#include "animcollection.hpp"

#include "../../AIsupport/mentalimage.hpp"
#include "../../../pes3/native_pose.hpp"

using namespace blunted;

class PlayerBase;
class Match;
namespace football_physics {class PhysicalRig;class ShirtCloth;struct Input;}

typedef std::map < const std::string, boost::intrusive_ptr<Node> > NodeMap;

struct Joint {
  boost::intrusive_ptr<Node> node;
  Vector3 position;
  Quaternion orientation;
  Vector3 origPos;
};

struct WeightedBone {
  int jointID;
  float weight;
};

struct WeightedVertex {
  int vertexID;
  std::vector<WeightedBone> bones;
};

struct FloatArray {
  float *data;
  int size;
};

enum e_InterruptAnim {
  e_InterruptAnim_None,
  e_InterruptAnim_Switch,
  e_InterruptAnim_Sliding,
  e_InterruptAnim_Bump,
  e_InterruptAnim_Trip,
  e_InterruptAnim_Cheat,
  e_InterruptAnim_Cancel,
  e_InterruptAnim_ReQueue
};

struct RotationSmuggle {
  RotationSmuggle() {
    begin = 0;
    end = 0;
  }
  void operator = (const float &value) {
    begin = value;
    end = value;
  }
  radian begin;
  radian end;
};

struct Anim {

  Anim() {
    id = 0;
    frameNum = 0;

    rotationSmuggle.begin = 0;
    rotationSmuggle.end = 0;
    rotationSmuggleOffset = 0;
    touchFrame = -1;
    touchMade = false;
    radiusOffset = 0.0;
  }

  Animation *anim;
  signed int id;
  int frameNum;

  e_FunctionType functionType;

  e_InterruptAnim originatingInterrupt;

  Vector3 fullActionSmuggle; // without cheatdiscarddistance
  Vector3 actionSmuggle;
  Vector3 actionSmuggleOffset;
  Vector3 actionSmuggleSustain;
  Vector3 actionSmuggleSustainOffset;
  Vector3 movementSmuggle;
  Vector3 movementSmuggleOffset;
  RotationSmuggle rotationSmuggle;
  radian rotationSmuggleOffset;
  signed int touchFrame;
  bool touchMade;
  float radiusOffset;
  Vector3 touchPos;

  Vector3 incomingMovement;
  Vector3 outgoingMovement;

  Vector3 positionOffset;

  PlayerCommand originatingCommand;

  std::vector<Vector3> positions;
};

struct IdealAnimDescription {
  IdealAnimDescription() {
    foot = e_Foot_Left;
    incomingVelocityFloat = 0.0f;
    outgoingMovementRel = Vector3(0, 0, 0);;
    incomingBodyDirectionRel = Vector3(0, -1, 0);
    desiredLookAtAbs = Vector3(0, 0, 0);
    baseAnim = false;
  }

  e_Foot foot;
  float incomingVelocityFloat;
  Vector3 outgoingMovementRel;
  Vector3 incomingBodyDirectionRel;
  Vector3 desiredLookAtAbs;
  bool baseAnim;
};

struct AnimApplyBuffer {
  AnimApplyBuffer() {
    frameNum = 0;
    snapshotTime_ms = 0;
    smooth = true;
    smoothFactor = 0.5f;
    noPos = false;
    orientation = 0;
    trainingTouchBlend = 0;
  }
  AnimApplyBuffer(const AnimApplyBuffer &src) {
    anim = src.anim;
    frameNum = src.frameNum;
    snapshotTime_ms = src.snapshotTime_ms;
    smooth = src.smooth;
    smoothFactor = src.smoothFactor;
    noPos = src.noPos;
    position = src.position;
    orientation = src.orientation;
    offsets = src.offsets;
    trainingTouchBlend = src.trainingTouchBlend;
    trainingTouchTarget = src.trainingTouchTarget;
    trainingTouchLeft = src.trainingTouchLeft;
    dribbleTrialBlend = src.dribbleTrialBlend;
    dribbleTrialPhase = src.dribbleTrialPhase;
    dribbleTrialLegBlend = src.dribbleTrialLegBlend;
    dribbleTrialFunction = src.dribbleTrialFunction;
    dribbleTrialFacing = src.dribbleTrialFacing;
    upperReception = src.upperReception; upperPhase=src.upperPhase; upperWeight=src.upperWeight; upperArmWeight=src.upperArmWeight;
  }
  Animation *anim;
  int frameNum;
  unsigned long snapshotTime_ms;
  bool smooth;
  float smoothFactor;
  bool noPos;
  Vector3 position;
  radian orientation;
  std::map < std::string, BiasedOffset > offsets;
  Animation *upperReception=nullptr;
  float upperPhase=0,upperWeight=0,upperArmWeight=0;
  float trainingTouchBlend = 0;
  Vector3 trainingTouchTarget;
  bool trainingTouchLeft = false;
  float dribbleTrialBlend = 0;
  float dribbleTrialPhase = 0;
  float dribbleTrialLegBlend = 0;
  int dribbleTrialFunction = 0;
  Quaternion dribbleTrialFacing = QUATERNION_IDENTITY;
};

struct TemporalHumanoidNode {
  boost::intrusive_ptr<Node> actualNode;
  Vector3 cachedPosition;
  Quaternion cachedOrientation;
  TemporalSmoother<Vector3> position;
  TemporalSmoother<Quaternion> orientation;
};

struct SpatialState {
  Vector3 position;
  radian angle;
  Vector3 directionVec; // for efficiency, vector version of angle
  e_Velocity enumVelocity;
  float floatVelocity; // for efficiency, float version

  Vector3 actualMovement;
  Vector3 physicsMovement; // ignores effects like positionoffset
  Vector3 animMovement;
  Vector3 movement; // one of the above (default)
  Vector3 actionSmuggleMovement;
  Vector3 movementSmuggleMovement;
  Vector3 positionOffsetMovement;

  radian bodyAngle;
  Vector3 bodyDirectionVec; // for efficiency, vector version of bodyAngle
  radian relBodyAngleNonquantized;
  radian relBodyAngle;
  Vector3 relBodyDirectionVec; // for efficiency, vector version of relBodyAngle
  Vector3 relBodyDirectionVecNonquantized;
  e_Foot foot;
};

static const Vector3 emptyVec(0);

class HumanoidBase {

  public:
    HumanoidBase(PlayerBase *player, Match *match, boost::intrusive_ptr<Node> humanoidSourceNode, boost::intrusive_ptr<Node> fullbodySourceNode, std::map<Vector3, Vector3> &colorCoords, boost::shared_ptr<AnimCollection> animCollection, boost::intrusive_ptr<Node> fullbodyTargetNode, boost::intrusive_ptr < Resource<Surface> > kit, int bodyUpdatePhaseOffset);
    virtual ~HumanoidBase();

    void PrepareFullbodyModel(std::map<Vector3, Vector3> &colorCoords);
    void UpdateFullbodyNodes();
    bool NeedsModelUpdate();
    void UpdateFullbodyModel(bool updateSrc = false);

    virtual void Process();
    void PreparePutBuffers(unsigned long snapshotTime_ms);
    void FetchPutBuffers(unsigned long putTime_ms);
    void Put();

    virtual void CalculateGeomOffsets();
    void ProcessDribbleLoop();
    void SampleDribbleLoop(float phase, Quaternion *local, Quaternion *global, Vector3 *positions,
                          const Vector3 *footOffsets = nullptr) const;
    Vector3 DribbleBallTarget(float phase, unsigned side) const;
    float DribbleShoeDistance(const Vector3 &point, unsigned side, Vector3 *closest = nullptr) const;
    void UpdateTrainingContactPose();
    bool UsesTrainingContacts() const;
    bool PhysicalRigEnabled() const;
    bool PhysicalRigBusy() const;
    void TogglePhysicalRig();
    void AddPhysicalImpulse(const Vector3 &impulse, const Vector3 &lever=Vector3(0,0,.35f),bool forceFall=false);
    void PhysicalCollision(const Vector3 &velocityChange);
  void ResetPhysicalRig(bool clearHistory=true);
  void PlanHeelPreparation();
    void UpdatePhysicalRigPose();
    void ProcessPhysicalMotion();
    void ProcessPhysicalPartner();
    void PutPhysicalRig();
    void ConfigurePhysicalRig();
    void SetPhysicalGrip(const Vector3 &point,const Vector3 &force);
    Vector3 PhysicalBalanceVelocity()const;
    bool PhysicalStaggering()const;
    bool PhysicalShielding()const {return physicalShield;}
    Vector3 PhysicalContactVelocity(const Vector3 &desired)const;
    void SetPhysicalTraction(const Vector3 &force) {physicalTraction=force;}
    void AddPhysicalTraction(const Vector3 &force) {physicalTraction+=force;if(physicalTraction.GetLength()>500)physicalTraction=physicalTraction.GetNormalized(0)*500;}
    Vector3 SafeFirstPersonEye(const Vector3 &eye,float clearance)const;
    void SetPhysicalShield(bool active) {physicalShield=active;}
    void SetPhysicalHandTarget(const Vector3 &point,bool active) {physicalHandTarget=point;physicalHandTargetActive=active;}
    float PhysicalHandDistance(const Vector3 &point)const;
    bool TackleLegContact(const HumanoidBase &victim,Vector3 &point)const;
    bool BodyContestContact(const HumanoidBase &other,Vector3 &point,Vector3 &normal,float &depth)const;
    Vector3 GetPhysicalShirtPoint()const;
    Vector3 GetPhysicalShirtPoint(const Vector3 &from)const;
    void PutShirtCloth(unsigned subgeom,std::vector<MaterializedTriangleMesh> &meshes);
    void PhysicalActionContact(const Vector3 &incoming);
    bool UpperReceptionActive() const {return upperReceptionClip!=nullptr;}
    void TickUpperReception();
    bool StartUpperReception(Animation *clip,int contactFrame);
    void BlendUpperReception(Animation *clip,float phase,float weight,radian facing,Quaternion *local,float armWeight=-1) const;
    void PutUpperReception();
    Vector3 GetStandingChestTarget() const;
    void CaptureContactMesh();
    void SampleContactAnimation(const Animation *animation, float phase, const Vector3 &root,
                               radian facing, bool source, Quaternion *local, Quaternion *global, Vector3 *positions) const;
    void ContactForwardKinematics(Quaternion *local, Quaternion *global, Vector3 *positions) const;
    float ContactSurface(const Vector3 &ballPosition, const std::string &part, const Quaternion *global,
                         const Vector3 *positions, Vector3 *closest = nullptr, std::string *hitPart = nullptr) const;
    void FitContactLeg(unsigned side, const Vector3 &offset, Quaternion *local, Quaternion *global, Vector3 *positions) const;
    void PutTrainingContactPose();
    void PutTrainingHeadLook();
    void AimTrainingHead(Quaternion *local, Quaternion *global, Vector3 *positions, const Vector3 &look) const;
    void ProcessTrainingBodyContact();
    void SetOffset(const std::string &nodeName, float bias, const Quaternion &orientation, bool isRelative = false);

    inline int GetFrameNum() { return currentAnim->frameNum; }
    inline int GetFrameCount() { return currentAnim->anim->GetFrameCount(); }

    inline Vector3 GetPosition() const { return spatialState.position; }
    inline Vector3 GetDirectionVec() const { return spatialState.directionVec; }
    inline Vector3 GetBodyDirectionVec() const { return spatialState.bodyDirectionVec; }
    inline radian GetAngle() const { return spatialState.angle; }
    inline radian GetRelBodyAngle() const { return spatialState.relBodyAngle; }
    inline e_Velocity GetEnumVelocity() const { return spatialState.enumVelocity; }
    inline e_FunctionType GetCurrentFunctionType() const { return currentAnim->functionType; }
    inline e_FunctionType GetPreviousFunctionType() const { return previousAnim->functionType; }
    inline Vector3 GetMovement() const { return spatialState.movement; }

    Vector3 GetGeomPosition() { return humanoidNode->GetPosition(); }

    int GetIdleMovementAnimID();
    void ResetPosition(const Vector3 &newPos, const Vector3 &focusPos, bool recovering=false);
    Vector3 GetContactFootPosition(unsigned side)const{return contactPositions[side?12:9];}
    void OffsetPosition(const Vector3 &offset);
    void TripMe(const Vector3 &tripVector, int tripType);

    boost::intrusive_ptr<Node> GetHumanoidNode() { return humanoidNode; }
    boost::intrusive_ptr<Node> GetFullbodyNode() { return fullbodyNode; }

    virtual float GetDecayingPositionOffsetLength() const { return decayingPositionOffset.GetLength(); }
    virtual float GetDecayingDifficultyFactor() const { return decayingDifficultyFactor; }

    const Anim *GetCurrentAnim() { return currentAnim; }
    const Anim *GetPreviousAnim() { return previousAnim; }

    const NodeMap &GetNodeMap() { return nodeMap; }

    void Hide() { fullbodyNode->SetPosition(Vector3(1000, 1000, -1000)); hairStyle->SetPosition(Vector3(1000, 1000, -1000)); } // hax ;)

    void SetKit(boost::intrusive_ptr < Resource<Surface> > newKit);

    virtual void ResetSituation(const Vector3 &focusPos);

  protected:
    bool _HighOrBouncyBall() const;
    void _KeepBestDirectionAnims(DataSet& dataset, const PlayerCommand &command, bool strict = true, radian allowedAngle = 0, int allowedVelocitySteps = 0, int forcedQuadrantID = -1); // ALERT: set sorting predicates before calling this function. strict kinda overrules the allowedstuff
    void _KeepBestBodyDirectionAnims(DataSet& dataset, const PlayerCommand &command, bool strict = true, radian allowedAngle = 0); // ALERT: set sorting predicates before calling this function. strict kinda overrules the allowedstuff
    virtual bool SelectAnim(const PlayerCommand &command, e_InterruptAnim localInterruptAnim, bool preferPassAndShot = false); // returns false on no applicable anim found
    void CalculatePredictedSituation(Vector3 &predictedPos, radian &predictedAngle);
    Vector3 CalculateOutgoingMovement(const std::vector<Vector3> &positions) const;

    void CalculateSpatialState(); // realtime properties, based on 'physics'
    void CalculateFactualSpatialState(); // realtime properties, based on anim. usable at last frame of anim. more riggid than above function

    void AddTripCommandToQueue(PlayerCommandQueue &commandQueue, const Vector3 &tripVector, int tripType);
    PlayerCommand GetTripCommand(const Vector3 &tripVector, int tripType);
    PlayerCommand GetBasicMovementCommand(const Vector3 &desiredDirection, float velocityFloat);

    void SetFootSimilarityPredicate(e_Foot desiredFoot) const;
    bool CompareFootSimilarity(int animIndex1, int animIndex2) const;
    void SetIncomingVelocitySimilarityPredicate(e_Velocity velocity) const;
    bool CompareIncomingVelocitySimilarity(int animIndex1, int animIndex2) const;
    void SetMovementSimilarityPredicate(const Vector3 &relDesiredDirection, e_Velocity desiredVelocity) const;
    float GetMovementSimilarity(int animIndex, const Vector3 &relDesiredDirection, e_Velocity desiredVelocity, float corneringBias) const;
    bool CompareMovementSimilarity(int animIndex1, int animIndex2) const;
    bool CompareDirectionSimilarity(int animIndex1, int animIndex2) const;
    bool CompareOutgoingVelocitySimilarity(int animIndex1, int animIndex2) const;
    void SetIncomingBodyDirectionSimilarityPredicate(const Vector3 &relIncomingBodyDirection) const;
    bool CompareIncomingBodyDirectionSimilarity(int animIndex1, int animIndex2) const;
    void SetBodyDirectionSimilarityPredicate(const Vector3 &lookAt) const;
    bool CompareBodyDirectionSimilarity(int animIndex1, int animIndex2) const;
    void SetTripDirectionSimilarityPredicate(const Vector3 &relDesiredTripDirection) const;
    bool CompareTripDirectionSimilarity(int animIndex1, int animIndex2) const;
    void SetBallDirectionSimilarityPredicate(const Vector3 &relDesiredBallDirection) const;
    bool CompareBallDirectionSimilarity(int animIndex1, int animIndex2) const;
    bool CompareBaseanimSimilarity(int animIndex1, int animIndex2) const;
    bool CompareCatchOrDeflect(int animIndex1, int animIndex2) const;
    void SetNumericVariableSimilarityPredicate(const std::string &varName, float desiredValue) const;
    bool CompareNumericVariable(int animIndex1, int animIndex2) const;

    Vector3 CalculatePhysicsVector(Animation *anim, bool useDesiredMovement, const Vector3 &desiredMovement, bool useDesiredBodyDirection, const Vector3 &desiredBodyDirectionRel, std::vector<Vector3> &positions_ret, radian &rotationOffset_ret) const;
    Vector3 CalculatePhysicsVector_disabled(Animation *anim, const Vector3 &desiredMovement, std::vector<Vector3> &positions_ret) const;

    Vector3 ForceIntoAllowedBodyDirectionVec(const Vector3 &src) const;
    radian ForceIntoAllowedBodyDirectionAngle(radian angle) const; // for making small differences irrelevant while sorting
    Vector3 ForceIntoPreferredDirectionVec(const Vector3 &src) const;
    radian ForceIntoPreferredDirectionAngle(radian angle) const;

    boost::intrusive_ptr<Node> fullbodyNode;
    std::vector<FloatArray> uniqueFullbodyMesh;
    std::vector < std::vector<WeightedVertex> > weightedVerticesVec; // < subgeoms < vertices > >
    unsigned int fullbodySubgeomCount;
    std::vector<int*> uniqueIndicesVec;
    std::vector<Joint> joints;
    Vector3 fullbodyOffset;
    boost::intrusive_ptr<Node> fullbodyTargetNode;

    boost::intrusive_ptr<Node> humanoidNode;
    boost::shared_ptr<Scene3D> scene3D;

    boost::intrusive_ptr<Geometry> hairStyle;

    std::string kitDiffuseTextureIdentString;

    Match *match;
    PlayerBase *player;

    boost::shared_ptr<AnimCollection> anims;
    NodeMap nodeMap;
    pes3::NativeBind pes3NativeReference{};
    bool pes3StudyWasApplied = false;
    float pes3RootCorrection = 0;
    std::unique_ptr<Animation> dribbleTrialAnimation;
    float dribbleTrialPhase = 0, dribbleTrialBlend = 0;
    float dribbleTrialSourceSpeed = 3.2055483f;
    float dribbleContactFrames[2] = {0,0};
    std::vector<std::array<Vector3,3>> dribbleShoeTriangles[2];
    Vector3 dribbleFootOffsets[2], fetchedDribbleFootOffsets[2];
    TemporalSmoother<Vector3> buf_dribbleFootOffsets[2];
    TemporalSmoother<Vector3> buf_dribbleRoot;
    Vector3 fetchedDribbleRoot;
    TemporalSmoother<float> buf_dribblePhase, buf_dribbleBlend;
    TemporalSmoother<Quaternion> buf_dribbleFacing;
    struct ContactTriangle { unsigned mesh; std::array<unsigned,3> vertices; std::string part; };
    std::vector<ContactTriangle> contactTriangles;
    std::array<int,13> contactJointBone{};
    std::unique_ptr<Animation> chestAnimation;
    float chestContactFrame = 33.333f;
    Vector3 contactPreviousBall;
    Quaternion contactPreviousSkinLocal[13];
    Vector3 contactPreviousSkinRoot;
    Animation *upperReceptionClip=nullptr;
    unsigned long upperReceptionStarted_ms=0;
    float upperReceptionPhase=0,upperReceptionWeight=0,upperReceptionArmWeight=0,upperReceptionArmRelease=-1;
    int upperReceptionContactFrame=0,upperReceptionEndFrame=0;
    bool upperReceptionTouchMade=false;
    bool contactPreviousBallValid=false;
    unsigned long bodyContactUntil_ms=0;
    TemporalSmoother<Vector3> buf_trainingLook;
    Vector3 fetchedTrainingLook;
    Quaternion contactLocal[13], contactGlobal[13];
    Vector3 contactPositions[13];
    float contactPoseBlend = 0, fetchedContactBlend = 0;
    TemporalSmoother<Quaternion> buf_contactLocal[13];
    TemporalSmoother<Vector3> buf_contactRoot;
    TemporalSmoother<float> buf_contactHeight, buf_contactBlend, buf_chestPhase;
    Quaternion fetchedContactLocal[13];
    Vector3 fetchedContactRoot;
    float fetchedContactHeight = 0, fetchedChestPhase = -1;
    std::unique_ptr<football_physics::PhysicalRig> physicalRig;
    unsigned long physicalRigTime=~0ul;
    unsigned long physicalCollisionTime=0;
    TemporalSmoother<float> buf_physicalRig;
    bool fetchedPhysicalRig=false;
    TemporalSmoother<Quaternion> buf_physicalAdditive[13];
    Quaternion fetchedPhysicalAdditive[13];
    bool fetchedPhysicalRagdoll=false;
    Vector3 physicalGripPoint{0},physicalGripForce{0};
    Vector3 physicalTraction{0};
    TemporalSmoother<Vector3> buf_physicalGripPoint,buf_physicalGripForce;
    Vector3 fetchedPhysicalGripPoint,fetchedPhysicalGripForce;
    std::vector<std::shared_ptr<football_physics::ShirtCloth>> shirtCloth;
    std::vector<unsigned long> shirtClothTime;
    unsigned long physicalActionTime=0;
    unsigned long physicalCutUntil=0,physicalIntentTime=~0ul,physicalBallImpactTime=0,physicalKeeperAttemptUntil=0,physicalHeelTime=0;
    Vector3 physicalBallImpactVelocity{0},physicalBallImpactPosition{0};
    std::string physicalBallImpactPart;
    Vector3 physicalPendingCut{0};
    void PhysicalDirectionChange(const Vector3 &desired);
    unsigned long physicalStaggerUntil=0;
    float physicalPartnerPhase=0;
    bool physicalShield=false;
    Vector3 physicalHandTarget{0};
    bool physicalHandTargetActive=false;
    unsigned physicalSituationProfile=0;
    TemporalSmoother<Vector3> buf_situationState;
    Vector3 fetchedSituationState{0};
    void BuildSituationalInput(football_physics::Input &input);
    void RankMotionMatches(DataSet &candidates,const PlayerCommand &command);

    AnimApplyBuffer animApplyBuffer;

    AnimApplyBuffer buf_animApplyBuffer;

    std::vector<TemporalHumanoidNode> buf_TemporalHumanoidNodes;

    bool buf_LowDetailMode;
    int buf_bodyUpdatePhase;
    int buf_bodyUpdatePhaseOffset;

    AnimApplyBuffer fetchedbuf_animApplyBuffer;

    unsigned long fetchedbuf_previousSnapshotTime_ms;

    bool fetchedbuf_LowDetailMode;
    int fetchedbuf_bodyUpdatePhase;
    int fetchedbuf_bodyUpdatePhaseOffset;

    std::map < std::string, BiasedOffset > offsets;

    Anim *currentAnim;
    Anim *previousAnim;

    // position/rotation offsets at the start of currentAnim
    Vector3 startPos;
    radian startAngle;

    // position/rotation offsets at the end of currentAnim
    Vector3 nextStartPos;
    radian nextStartAngle;

    // realtime info
    SpatialState spatialState;

    Vector3 previousPosition2D;

    e_InterruptAnim interruptAnim;
    int reQueueDelayFrames;
    int tripType;
    Vector3 tripDirection;

    Vector3 decayingPositionOffset;
    float decayingDifficultyFactor;

    // for comparing dataset entries (needed by std::list::sort)
    mutable e_Foot predicate_DesiredFoot;
    mutable e_Velocity predicate_IncomingVelocity;
    mutable Vector3 predicate_RelDesiredDirection;
    mutable Vector3 predicate_DesiredDirection;
    mutable float predicate_CorneringBias;
    mutable e_Velocity predicate_DesiredVelocity;
    mutable Vector3 predicate_RelIncomingBodyDirection;
    mutable Vector3 predicate_LookAt;
    mutable Vector3 predicate_RelDesiredTripDirection;
    mutable Vector3 predicate_RelDesiredBallDirection;
    mutable std::string predicate_NumericVariableName;
    mutable float predicate_NumericVariableValue;

    const MentalImage *currentMentalImage;

    float _cache_AgilityFactor;
    float _cache_AccelerationFactor;

    float zMultiplier;

    std::vector<Vector3> allowedBodyDirVecs;
    std::vector<radian> allowedBodyDirAngles;
    std::vector<Vector3> preferredDirectionVecs;
    std::vector<radian> preferredDirectionAngles;

    MovementHistory movementHistory;

};

#endif
