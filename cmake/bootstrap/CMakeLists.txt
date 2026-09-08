cmake_minimum_required(VERSION 3.25)
project(TDMDependencies LANGUAGES C CXX)
include(ExternalProject)
find_package(Python3 3.9 REQUIRED COMPONENTS Interpreter)
include("${CMAKE_CURRENT_LIST_DIR}/../FetchLocked.cmake")
foreach(name IN ITEMS boost openssl flatbuffers)
  tdm_archive(${name})
endforeach()

foreach(name IN ITEMS boost openssl)
  ExternalProject_Add(build_${name}
    SOURCE_DIR "${${name}_SOURCE_DIR}" DOWNLOAD_COMMAND "" UPDATE_COMMAND ""
    CONFIGURE_COMMAND "" INSTALL_COMMAND "" BUILD_IN_SOURCE TRUE
    BUILD_COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_LIST_DIR}/../../scripts/build_dependency.py"
      ${name} --source "${${name}_SOURCE_DIR}" --prefix "${TDM_DEPS_PREFIX}"
      --arch "${TDM_ARCH}" --deployment-target "${TDM_MACOS_MIN}")
endforeach()

set(host_args)
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
  # The pinned flatc has unused variables in its Rust generator. Newer GCC
  # diagnoses these, and flatc's own -Werror would stop the bootstrap build.
  list(APPEND host_args "-DCMAKE_CXX_FLAGS=-Wno-error=unused-but-set-variable")
endif()
if(APPLE)
  list(APPEND host_args "-DCMAKE_OSX_ARCHITECTURES=${CMAKE_HOST_SYSTEM_PROCESSOR}")
endif()
ExternalProject_Add(build_flatc
  SOURCE_DIR "${flatbuffers_SOURCE_DIR}" DOWNLOAD_COMMAND "" UPDATE_COMMAND ""
  CMAKE_GENERATOR Ninja
  CMAKE_ARGS -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5
    -DFLATBUFFERS_BUILD_TESTS=OFF -DFLATBUFFERS_BUILD_FLATLIB=OFF -DFLATBUFFERS_BUILD_FLATHASH=OFF
    -DFLATBUFFERS_BUILD_FLATC=ON -DFLATBUFFERS_INSTALL=ON "-DCMAKE_INSTALL_PREFIX=${TDM_DEPS_PREFIX}/host" ${host_args}
  BUILD_COMMAND "${CMAKE_COMMAND}" --build <BINARY_DIR> --config Release --target flatc
  INSTALL_COMMAND "${CMAKE_COMMAND}" --install <BINARY_DIR> --config Release)
