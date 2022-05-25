#include <regex>

#include "tiledbsc/soma.h"

namespace tiledbsc {
using namespace std;
using namespace tiledb;

//===================================================================
//= public static
//===================================================================
SOMA SOMA::open(string_view uri) {
    return SOMA(uri);
}

//===================================================================
//= public non-static
//===================================================================
SOMA::SOMA(string_view uri) {
    // Remove all trailing /
    uri_ = regex_replace(string(uri), regex("/+$"), "");
}

map<string, string> SOMA::list_arrays() {
    Group group(ctx_, uri_, TILEDB_READ);
    build_uri_map(group);
    return uri_map_;
}

//===================================================================
//= private non-static
//===================================================================
void SOMA::build_uri_map(Group& group, string_view parent) {
    // Iterate through all members in the group
    for (uint64_t i = 0; i < group.member_count(); i++) {
        auto member = group.member(i);
        auto path = parent.empty() ?
                        member.name().value() :
                        string(parent) + "/" + member.name().value();

        if (member.type() == Object::Type::Group) {
            // Member is a group, call recursively
            auto subgroup = Group(ctx_, member.uri(), TILEDB_READ);
            build_uri_map(subgroup, path);
        } else {
            auto uri = member.uri();
            if (is_tiledb_uri(uri) && !is_tiledb_uri(uri_)) {
                // Member uri is registered on tiledb://, but the root uri is
                // not from tiledb://, build a relative uri
                uri_map_[path] = uri_ + '/' + path;
                group_uri_override_ = true;
            } else {
                // Use the group member uri
                uri_map_[path] = uri;
            }
        }
    }
}
};  // namespace tiledbsc