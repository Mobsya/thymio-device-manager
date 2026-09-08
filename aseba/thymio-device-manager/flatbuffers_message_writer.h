#pragma once
#include <boost/asio.hpp>
#include <boost/beast/core.hpp>
#include <aseba/flatbuffers/thymio_generated.h>
#include <memory>

namespace mobsya {

template <class AsyncWriteStream, class Handler>
class write_flatbuffer_message_op;


using write_flatbuffer_message_op_cb_t = void(boost::system::error_code);

template <class AsyncWriteStream, class CompletionToken>
BOOST_ASIO_INITFN_RESULT_TYPE(CompletionToken, write_flatbuffer_message_op_cb_t)
async_write_flatbuffer_message(AsyncWriteStream& stream, const flatbuffers::DetachedBuffer& buffer,
                               CompletionToken&& token) {
    static_assert(boost::beast::is_async_write_stream<AsyncWriteStream>::value,
                  "AsyncWriteStream requirements not met");

    boost::asio::async_completion<CompletionToken, write_flatbuffer_message_op_cb_t> init{token};
    write_flatbuffer_message_op<AsyncWriteStream,
                                BOOST_ASIO_HANDLER_TYPE(CompletionToken, write_flatbuffer_message_op_cb_t)>{
        stream, std::move(buffer), init.completion_handler}();

    return init.result.get();
}


template <class AsyncWriteStream, class Handler>
class write_flatbuffer_message_op {
    struct state {
        AsyncWriteStream& stream;
        Handler handler;
        const flatbuffers::DetachedBuffer& buffer;
        uint32_t size;

        template <class DeducedHandler>
        explicit state(AsyncWriteStream& stream, const flatbuffers::DetachedBuffer& buffer, DeducedHandler&& handler)
            : stream(stream), handler(std::forward<DeducedHandler>(handler)), buffer(buffer), size(uint32_t(buffer.size())) {}
    };
    std::shared_ptr<state> m_p;

public:
    write_flatbuffer_message_op(write_flatbuffer_message_op&&) = default;
    write_flatbuffer_message_op(write_flatbuffer_message_op const&) = default;

    template <class DeducedHandler, class... Args>
    write_flatbuffer_message_op(AsyncWriteStream& stream, const flatbuffers::DetachedBuffer& buffer,
                                DeducedHandler&& handler)
        : m_p(std::make_shared<state>(stream, buffer, std::forward<DeducedHandler>(handler))) {}

    using allocator_type = boost::asio::associated_allocator_t<Handler>;

    allocator_type get_allocator() const noexcept {
        return boost::asio::get_associated_allocator(m_p->handler);
    }

    using executor_type =
        boost::asio::associated_executor_t<Handler, decltype(std::declval<AsyncWriteStream&>().get_executor())>;

    executor_type get_executor() const noexcept {
        return (boost::asio::get_associated_executor)(m_p->handler, m_p->stream.get_executor());
    }

    void operator()() {
        auto& state = *m_p;
        return boost::asio::async_write(
            state.stream,
            std::vector<boost::asio::const_buffer>{boost::asio::buffer(&state.size, 4),
                                                   boost::asio::buffer(state.buffer.data(), state.buffer.size())},

            std::move(*this));
    }

    void operator()(boost::system::error_code ec, std::size_t) {
        auto handler = std::move(m_p->handler);
        m_p.reset();
        handler(ec);
    }
};

}  // namespace mobsya
