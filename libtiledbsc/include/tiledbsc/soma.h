#ifndef SOMA_H
#define SOMA_H

#include <tiledb/tiledb>
#include <tiledb/tiledb_experimental>

namespace tiledbsc {
using namespace tiledb;
using namespace std;

class SOMA {
   public:
    //===================================================================
    //= public static
    //===================================================================
    static SOMA open(string_view uri);

    //===================================================================
    //= public non-static
    //===================================================================
    SOMA(string_view uri);

    map<string, string> list_arrays();

   private:
    //===================================================================
    //= private static
    //===================================================================

    //===================================================================
    //= private non-static
    //===================================================================
    Context ctx_;
    string uri_;
    bool group_uri_override_ = false;
    map<string, string> uri_map_;

    void build_uri_map(Group& group, string_view parent = "");

    bool is_tiledb_uri(string_view uri) {
        return uri.find("tiledb://") == 0;
    }
};

};  // namespace tiledbsc

#endif