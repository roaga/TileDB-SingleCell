#include <tiledbsc/soma.h>
#include <tiledbsc/soma_collection.h>
#include <tiledbsc/tiledbsc.h>

using namespace tiledbsc;

void walk_soco(string_view uri) {
    auto soco = SOMACollection::open(uri);
    auto somas = soco.list_somas();

    for (auto& [name, uri] : somas) {
        printf("soma %s = %s\n", name.c_str(), uri.c_str());

        auto soma = SOMA::open(uri);
        auto arrays = soma.list_arrays();
        for (auto& [name, uri] : arrays) {
            printf("  array %s = %s\n", name.c_str(), uri.c_str());
        }
    }
}

int main(int argc, char** argv) {
    (void)argc;

    try {
        walk_soco(argv[1]);
    } catch (const std::exception& e) {
        printf("ERROR: %s\n", e.what());
    }

    return 0;
};