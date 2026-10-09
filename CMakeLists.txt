# Football Training: maintained build, runtime staging and controller validation.
cmake_minimum_required(VERSION 3.16)
if(POLICY CMP0167)
  cmake_policy(SET CMP0167 NEW)
endif()

set(PACKAGE GameplayFootball)

set(VERSION_MAJOR 0)
set(VERSION_MINOR 3)
set(VERSION_PATCH 0)
if(${VERSION_PATCH})
   set(VERSION ${VERSION_MAJOR}.${VERSION_MINOR}.${VERSION_PATCH})
else(${VERSION_PATCH})
   set(VERSION ${VERSION_MAJOR}.${VERSION_MINOR})
endif(${VERSION_PATCH})

set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${CMAKE_SOURCE_DIR}/CMakeModules")

project(GameplayFootball)

set (CMAKE_CXX_STANDARD 14)

if(UNIX)
   set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -g -Wall")
   # Temporarily suppress warnings during debug
   set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -Wno-unused-variable -Wno-sign-compare -Wno-unused-function -Wno-strict-aliasing")
   set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -Wall -O3")
endif(UNIX)
# SET(CMAKE_CXX_FLAGS  "${CMAKE_CXX_FLAGS} ${GCC_COVERAGE_COMPILE_FLAGS} -fPIC -g -O3")
# SET(CMAKE_C_FLAGS  "${CMAKE_C_FLAGS} -fPIC -O3 -g")

# Find required libraries
FIND_PACKAGE(OpenGL REQUIRED)
include_directories(${OPENGL_INCLUDE_DIR})

FIND_PACKAGE(SDL2 2.24 REQUIRED)
include_directories(${SDL2_INCLUDE_DIR})

FIND_PACKAGE(SDL2_image REQUIRED)
include_directories(${SDL2_IMAGE_DIRS})

FIND_PACKAGE(SDL2_ttf REQUIRED)
include_directories(${SDL2_TTF_DIRS})

FIND_PACKAGE(SDL2_gfx REQUIRED)
include_directories(${SDL2_GFX_DIRS})

FIND_PACKAGE(Boost REQUIRED COMPONENTS system thread filesystem)
include_directories(${Boost_INCLUDE_DIR})

FIND_PACKAGE(OpenAL REQUIRED)
include_directories(${OPENAL_INCLUDE_DIR})

FIND_PACKAGE(SQLite3 REQUIRED)
include_directories(${SQLite3_INCLUDE_DIRS})

include_directories(${PROJECT_SOURCE_DIR}/src)
add_compile_definitions(BOOST_BIND_GLOBAL_PLACEHOLDERS)

# Include the sources
include(sources.cmake)

# Compile it as multiple static libraries (note: not compiling physics,
# as not used by gameplayfootball)

add_library(baselib OBJECT ${BASE_SOURCES} ${BASE_HEADERS}
        ${BASE_GEOMETRY_HEADERS} ${BASE_MATH_HEADERS})
add_library(systemscommonlib OBJECT ${SYSTEMS_COMMON_SOURCES}
        ${SYSTEMS_COMMON_HEADERS})
add_library(systemsgraphicslib OBJECT ${SYSTEMS_GRAPHICS_SOURCES}
        ${SYSTEMS_GRAPHICS_HEADERS} ${SYSTEMS_GRAPHICS_OBJECTS_HEADERS}
        ${SYSTEMS_GRAPHICS_RESOURCES_HEADERS} ${SYSTEMS_GRAPHICS_RENDERING_HEADERS})
add_library(systemsaudiolib OBJECT ${SYSTEMS_AUDIO_SOURCES}
        ${SYSTEMS_AUDIO_HEADERS} ${SYSTEMS_AUDIO_OBJECTS_HEADERS}
        ${SYSTEMS_AUDIO_RESOURCES_HEADERS} ${SYSTEMS_AUDIO_RENDERING_HEADERS})
add_library(loaderslib OBJECT ${LOADERS_SOURCES} ${LOADERS_HEADERS})
add_library(typeslib OBJECT ${TYPES_SOURCES} ${TYPES_HEADERS})
add_library(frameworklib OBJECT ${FRAMEWORK_SOURCES} ${FRAMEWORK_HEADERS})
add_library(scenelib OBJECT ${SCENE_SOURCES} ${SCENE_HEADERS}
        ${SCENE2D_HEADERS} ${SCENE3D_HEADERS} ${SCENE_OBJECTS_HEADERS}
        ${SCENE_RESOURCES_HEADERS})
add_library(managerslib OBJECT ${MANAGERS_SOURCES} ${MANAGERS_HEADERS})
add_library(utilslib OBJECT ${UTILS_SOURCES} ${UTILS_HEADERS}
        ${UTILS_EXT_HEADERS})
add_library(gui2lib OBJECT ${UTILS_GUI2_SOURCES} ${UTILS_GUI2_HEADERS}
        ${UTILS_GUI2_WIDGETS_HEADERS})

set(OWN_LIBRARIES $<TARGET_OBJECTS:baselib> $<TARGET_OBJECTS:systemscommonlib>
        $<TARGET_OBJECTS:systemsgraphicslib>
        $<TARGET_OBJECTS:systemsaudiolib> $<TARGET_OBJECTS:loaderslib>
        $<TARGET_OBJECTS:typeslib> $<TARGET_OBJECTS:frameworklib>
        $<TARGET_OBJECTS:scenelib> $<TARGET_OBJECTS:managerslib>
        $<TARGET_OBJECTS:utilslib> $<TARGET_OBJECTS:gui2lib>)

# Join all created static libraries into the single static one.
add_library(blunted2 ${BLUNTED_CORE_SOURCES} ${BLUNTED_CORE_HEADERS} ${OWN_LIBRARIES})

add_library(leaguelib ${LEAGUE_SOURCES} ${LEAGUE_HEADERS})
add_library(gamelib ${GAME_SOURCES} ${GAME_HEADERS})
target_sources(gamelib PRIVATE src/onthepitch/training.cpp)
add_library(hidlib ${HID_SOURCES} ${HID_HEADERS})
add_library(menulib ${MENU_SOURCES} ${MENU_HEADERS})
add_library(datalib ${DATA_SOURCES} ${DATA_HEADERS})

if(TARGET SQLite::SQLite3)
   set(SQLITE_TARGET SQLite::SQLite3)
elseif(TARGET unofficial::sqlite3::sqlite3)
   set(SQLITE_TARGET unofficial::sqlite3::sqlite3)
else()
   set(SQLITE_TARGET ${SQLite3_LIBRARIES})
endif()

if(WIN32)
   set(PLATFORM_LIBRARIES opengl32 ws2_32)
else()
   set(PLATFORM_LIBRARIES dl m)
endif()

# SDL's CMake package prepends SDL2main to SDL2_LIBRARIES on Windows.  The
# project supplies its own native entry point (and deliberately undefines
# SDL's main macro), so linking SDL2main would create an unresolved SDL_main
# symbol.  Link the SDL2 runtime target directly for the Windows build and
# retain the legacy variable for older Linux package files.
if(WIN32 AND TARGET SDL2::SDL2)
   set(SDL2_RUNTIME_LIBRARY SDL2::SDL2)
else()
   set(SDL2_RUNTIME_LIBRARY ${SDL2_LIBRARIES})
endif()

set(LIBRARIES gamelib hidlib menulib datalib leaguelib blunted2
   Boost::filesystem Boost::system Boost::thread ${SQLITE_TARGET}
   ${SDL2_IMAGE_LIBRARIES} ${SDL2_TTF_LIBRARIES} ${SDL2_GFX_LIBRARIES}
   ${SDL2_RUNTIME_LIBRARY} ${OPENAL_LIBRARY} ${PLATFORM_LIBRARIES} ${OPENGL_LIBRARIES})

add_executable(gameplayfootball WIN32 ${CORE_SOURCES} ${CORE_HEADERS})
target_sources(gameplayfootball PRIVATE tests/controller_tests.cpp)
target_link_libraries(gameplayfootball ${LIBRARIES})

find_package(Python3 COMPONENTS Interpreter REQUIRED)
add_custom_command(TARGET gameplayfootball POST_BUILD
  COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/scripts/prepare_runtime.py ${CMAKE_CURRENT_BINARY_DIR})
enable_testing()
add_test(NAME xbox_controller COMMAND gameplayfootball --test-controller)
