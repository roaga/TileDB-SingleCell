#ifndef SOMA_COLLECTION_H
#define SOMA_COLLECTION_H

#include <tiledb/tiledb>
#include <tiledb/tiledb_experimental>

namespace tiledbsc {
using namespace tiledb;
using namespace std;

class SOMACollection {
   public:
    //===================================================================
    //= public static
    //===================================================================
    static SOMACollection open(string_view uri);

    //===================================================================
    //= public non-static
    //===================================================================
    SOMACollection(string_view uri);

    map<string, string> list_somas();

   private:
    //===================================================================
    //= private static
    //===================================================================

    //===================================================================
    //= private non-static
    //===================================================================
    Context ctx_;
    string uri_;
    map<string, string> uri_map_;

    void build_uri_map(Group& group);

    bool is_tiledb_uri(string_view uri) {
        return uri.find("tiledb://") == 0;
    }
};

};  // namespace tiledbsc

#endif