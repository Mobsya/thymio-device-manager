set(header "${CMAKE_CURRENT_BINARY_DIR}/thymio_generated.h")
add_custom_command(OUTPUT "${header}"
  COMMAND "${TDM_FLATC}" --cpp --no-includes --gen-mutable --scoped-enums --gen-object-api
    --cpp-ptr-type std::unique_ptr -o "${CMAKE_CURRENT_BINARY_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}/thymio.fbs"
  DEPENDS "${TDM_FLATC}" "${CMAKE_CURRENT_SOURCE_DIR}/thymio.fbs" VERBATIM)
add_library(thymio-flatbuffers STATIC thymio-flatbuffers.cpp "${header}" fb_message_ptr.h)
target_link_libraries(thymio-flatbuffers PUBLIC flatbuffers aseba_conf)
target_include_directories(thymio-flatbuffers PUBLIC "${CMAKE_BINARY_DIR}")
