#pragma once
#include <boost/asio.hpp>
#include <boost/beast/core.hpp>
#include <aseba/flatbuffers/thymio_generated.h>
#include <aseba/flatbuffers/fb_message_ptr.h>
#include <memory>
#include "log.h"
#include "tdm.h"

namespace mobsya {

template <class AsyncReadStream, class Handler>
class read_flatbuffers_message_op;

using read_flatbuffers_message_op_cb_t = void(boost::system::error_code, fb_message_ptr);

template <class AsyncReadStream, class CompletionToken>
BOOST_ASIO_INITFN_RESULT_TYPE(CompletionToken, read_flatbuffers_message_op_cb_t)
async_read_flatbuffers_message(AsyncReadStream& stream, CompletionToken&& token) {
    static_assert(boost::beast::is_async_read_stream<AsyncReadStream>::value, "AsyncReadStream requirements not met");

    boost::asio::async_completion<CompletionToken, read_flatbuffers_message_op_cb_t> init{token};
    read_flatbuffers_message_op<AsyncReadStream,
                                BOOST_ASIO_HANDLER_TYPE(CompletionToken, read_flatbuffers_message_op_cb_t)>{
        stream, std::forward<CompletionToken>(init.completion_handler)}();

    return init.result.get();
}


template <class AsyncReadStream, class Handler>
class read_flatbuffers_message_op {
    struct state {
        AsyncReadStream& stream;
        Handler handler;
        char sizeBuffer[4];
        std::vector<uint8_t> dataBuffer;

        template <class DeducedHandler>
        explicit state(AsyncReadStream& stream, DeducedHandler&& handler)
            : stream(stream), handler(std::forward<DeducedHandler>(handler)) {}
    };
    std::shared_ptr<state> m_p;

public:
    read_flatbuffers_message_op(read_flatbuffers_message_op&&) = default;
    read_flatbuffers_message_op(read_flatbuffers_message_op const&) = default;

    template <class DeducedHandler, class... Args>
    read_flatbuffers_message_op(AsyncReadStream& stream, DeducedHandler&& handler)
        : m_p(std::make_shared<state>(stream, std::forward<DeducedHandler>(handler))) {}

    using allocator_type = boost::asio::associated_allocator_t<Handler>;

    allocator_type get_allocator() const noexcept {
        return boost::asio::get_associated_allocator(m_p->handler);
    }

    using executor_type =
        boost::asio::associated_executor_t<Handler, decltype(std::declval<AsyncReadStream&>().get_executor())>;

    executor_type get_executor() const noexcept {
        return boost::asio::get_associated_executor(m_p->handler, m_p->stream.get_executor());
    }

    void operator()() {
        auto& state = *m_p;
        return boost::asio::async_read(state.stream, boost::asio::buffer(state.sizeBuffer),
                                       boost::asio::transfer_exactly(4), std::move(*this));
    }

    void operator()(boost::system::error_code ec, std::size_t bytes_transferred) {
        if(ec)
            mLogError("{}", ec.message());
        if(ec || bytes_transferred == 0)
            return;
        auto& state = *m_p;
        if(state.dataBuffer.size() == 0) {
            assert(bytes_transferred == 4);
            auto size = reinterpret_cast<uint32_t&>(state.sizeBuffer);
            if(size > tdm::maxAppEndPointMessageSize) {
                auto handler = std::move(m_p->handler);
                m_p.reset();
                handler(boost::asio::error::make_error_code(boost::asio::error::message_size), fb_message_ptr{});
                return;
            }
            state.dataBuffer.resize(size);
            return boost::asio::async_read(
                state.stream, boost::asio::buffer(state.dataBuffer),
                boost::asio::transfer_exactly(std::min(size, tdm::maxAppEndPointMessageSize)), std::move(*this));
        }
        if(bytes_transferred != state.dataBuffer.size()) {
            auto handler = std::move(m_p->handler);
            m_p.reset();
            handler(ec, fb_message_ptr{});
            return;
        }
        auto& b = state.dataBuffer;
        flatbuffers::Verifier verifier(b.data(), b.size());
        if(!fb::VerifyMessageBuffer(verifier)) {
            auto handler = std::move(m_p->handler);
            m_p.reset();
            handler(boost::system::errc::make_error_code(boost::system::errc::bad_message), fb_message_ptr{});
            return;
        }
        auto handler = std::move(m_p->handler);
        auto message = fb_message_ptr(std::move(b));
        m_p.reset();
        handler(ec, std::move(message));
    }
};
}  // namespace mobsya
