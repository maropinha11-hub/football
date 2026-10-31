#include "base/read_lines.hpp"
#include "utils/packed_animation.hpp"
#include <sstream>
#include <iostream>
#include <fstream>
int main(int argc,char **argv){
  if(argc==2){
    try{
      std::ifstream source(argv[1],std::ios::binary);std::vector<std::string> lines;
      if(!blunted::readPackedAnimation(source,lines))return 2;
      for(const auto &line:lines)std::cout<<line<<'\n';
      return 0;
    }catch(const std::exception &error){std::cerr<<error.what()<<'\n';return 3;}
  }
  // Dense long captures exceed the legacy 32767-byte C string. Metadata
  // after that row must survive: losing <type> caused an invalid map access.
  const std::string pose(100000,'7');
  std::istringstream source(pose+"\r\n<type>movement</type>\n<loop>false</loop>");
  std::vector<std::string> lines;blunted::readTextLines(source,lines);
  const bool ok=lines.size()==3&&lines[0]==pose&&lines[1]=="<type>movement</type>"&&lines[2]=="<loop>false</loop>";
  std::cout<<"{\"checks\":1,\"failures\":"<<(ok?0:1)<<"}\n";
  return ok?0:1;
}
