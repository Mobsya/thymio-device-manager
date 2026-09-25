#include <aseba/thymio-device-manager/usbcontext.h>
#include <chrono>
#include <cstdlib>
#include <iostream>

namespace {
int init_error = LIBUSB_ERROR_OTHER;
int init_calls = 0;
int exit_calls = 0;
std::atomic<int> event_calls{0};
int context_storage;

libusb_context* expected_context() {
    return reinterpret_cast<libusb_context*>(&context_storage);
}
}

// A failed libusb_init does not provide a usable context. Neither the event
// thread nor cleanup may call libusb with it, regardless of the failure code.
extern "C" int __wrap_libusb_init(libusb_context** context) {
    ++init_calls;
    if(init_error == LIBUSB_SUCCESS)
        *context = expected_context();
    return init_error;
}

extern "C" int __wrap_libusb_handle_events_timeout(libusb_context* context, timeval*) {
    if(init_error != LIBUSB_SUCCESS || context != expected_context()) {
        std::cerr << "USB event processing used an uninitialized context\n";
        std::abort();
    }
    ++event_calls;
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
    return LIBUSB_SUCCESS;
}

extern "C" void __wrap_libusb_exit(libusb_context* context) {
    if(init_error != LIBUSB_SUCCESS || context != expected_context()) {
        std::cerr << "USB cleanup used an uninitialized context\n";
        std::abort();
    }
    ++exit_calls;
}

int main() {
    for(int error : {LIBUSB_ERROR_OTHER, LIBUSB_ERROR_ACCESS}) {
        init_error = error;
        try {
            auto context = mobsya::details::usb_context::acquire_context();
            std::cerr << "USB initialization failure was ignored\n";
            return 1;
        } catch(const boost::system::system_error& e) {
            if(e.code() != mobsya::usb::make_error_code(error)) {
                std::cerr << "USB initialization reported the wrong error: " << e.what() << '\n';
                return 1;
            }
        }
    }

    // A later successful initialization must still share one context and run
    // its event thread until the last owner releases it.
    init_error = LIBUSB_SUCCESS;
    {
        auto context = mobsya::details::usb_context::acquire_context();
        auto second_owner = mobsya::details::usb_context::acquire_context();
        if(context != second_owner || init_calls != 3) {
            std::cerr << "USB context was not shared after successful initialization\n";
            return 1;
        }
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
        while(event_calls == 0 && std::chrono::steady_clock::now() < deadline)
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        if(event_calls == 0) {
            std::cerr << "USB event processing did not start\n";
            return 1;
        }
    }
    if(exit_calls != 1) {
        std::cerr << "USB context was not released exactly once\n";
        return 1;
    }
}
