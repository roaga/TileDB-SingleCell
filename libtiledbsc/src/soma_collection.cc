#include <regex>

#include "tiledbsc/soma_collection.h"

namespace tiledbsc {
using namespace std;
using namespace tiledb;

//===================================================================
//= public static
//===================================================================
SOMACollection SOMACollection::open(string_view uri) {
    return SOMACollection(uri);
}

//===================================================================
//= public non-static
//===================================================================
SOMACollection::SOMACollection(string_view uri) {
    // Remove all trailing /
    uri_ = regex_replace(string(uri), regex("/+$"), "");
}

map<string, string> SOMACollection::list_somas() {
    Group group(ctx_, uri_, TILEDB_READ);
    build_uri_map(group);
    return uri_map_;
}

//===================================================================
//= private non-static
//===================================================================
void SOMACollection::build_uri_map(Group& group) {
    // Iterate through all members in the group
    for (uint64_t i = 0; i < group.member_count(); i++) {
        auto member = group.member(i);
        auto path = member.name().value();
        auto uri = member.uri();

        // Since SOCO members may reference tiledb:// or file:// SOMAs outside
        // of the SOCO relative directory structure, do not manipulate the group
        // member uri path like we do in SOMA
        uri_map_[path] = uri;
    }
}
};  // namespace tiledbsc