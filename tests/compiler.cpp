#include <aseba/compiler/compiler.h>
#include <catch2/catch.hpp>
#include <sstream>

TEST_CASE("The extracted compiler emits bytecode and rejects invalid programs") {
    Aseba::TargetDescription target;
    target.bytecodeSize = 1024;
    target.variablesSize = 256;
    target.stackSize = 32;
    Aseba::CommonDefinitions definitions;
    Aseba::Compiler compiler;
    compiler.setTargetDescription(&target);
    compiler.setCommonDefinitions(&definitions);
    Aseba::BytecodeVector bytecode;
    Aseba::Error error;
    unsigned variables = 0;
    SECTION("valid program") {
        std::wistringstream source(L"var result = 1 + 2\n");
        REQUIRE(compiler.compile(source, bytecode, variables, error));
        REQUIRE(variables == 1);
        REQUIRE_FALSE(bytecode.empty());
        bool hasThree = false;
        for (const auto& word : bytecode) {
            if (word.bytecode == 0x1003) hasThree = true; // PUSH_SMALL_IMMEDIATE 3
        }
        REQUIRE(hasThree);
    }
    SECTION("undefined variable") {
        std::wistringstream source(L"missing_variable = 42\n");
        REQUIRE_FALSE(compiler.compile(source, bytecode, variables, error));
        REQUIRE_FALSE(error.message.empty());
    }
}
