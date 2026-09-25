add_subdirectory(common)
add_subdirectory(msg)
add_subdirectory(thymio-device-manager)
add_executable(tst_compiler compiler.cpp thymio-device-manager/runner.cpp)
target_link_libraries(tst_compiler PRIVATE asebacompiler catch2)
add_test(NAME compiler COMMAND tst_compiler)
add_executable(protocol-probe protocol.cpp)
target_link_libraries(protocol-probe PRIVATE thymio-flatbuffers Boost::asio)
if(WIN32)
  target_link_libraries(protocol-probe PRIVATE ws2_32)
endif()
add_test(NAME daemon-smoke COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/smoke.py"
  "$<TARGET_FILE:thymio-device-manager>" "$<TARGET_FILE:protocol-probe>")
set_tests_properties(daemon-smoke PROPERTIES TIMEOUT 60 RUN_SERIAL TRUE)

if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
  add_executable(tst_usb_context usb_context.cpp)
  target_link_libraries(tst_usb_context PRIVATE thymio-device-manager-lib)
  target_link_options(tst_usb_context PRIVATE
    "LINKER:--wrap=libusb_init"
    "LINKER:--wrap=libusb_exit"
    "LINKER:--wrap=libusb_handle_events_timeout")
  add_test(NAME usb-init-failure COMMAND tst_usb_context)
  set_tests_properties(usb-init-failure PROPERTIES TIMEOUT 10)
endif()
