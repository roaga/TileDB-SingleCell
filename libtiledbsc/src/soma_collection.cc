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
void SOMACollection::build_uri_map(Group& group, string_view parent) {
    // Iterate through all members in the group
    for (uint64_t i = 0; i < group.member_count(); i++) {
        auto member = group.member(i);
        auto path = parent.empty() ?
                        member.name().value() :
                        string(parent) + "/" + member.name().value();

        if (member.type() == Object::Type::Group) {
            auto subgroup = Group(ctx_, member.uri(), TILEDB_READ);

            // TODO: Check group metadata to see if subgroup is a SOMA or SOCO
            // For now, infer the group is a SOMA if it contains an obs array
            if (subgroup.member("obs").type() == Object::Type::Array) {
                // Since SOCO members may reference tiledb:// or file://
                // SOMAs outside of the SOCO relative directory structure,
                // do not manipulate the group member uri like we do in SOMA
                uri_map_[path] = member.uri();
            } else {
                // Member is a SOCO, call recursively
                build_uri_map(subgroup);
            }
        }
    }
}
};  // namespace tiledbsc