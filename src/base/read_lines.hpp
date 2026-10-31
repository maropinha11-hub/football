#pragma once
#include <algorithm>
#include <istream>
#include <stdexcept>
#include <string>
#include <vector>

namespace blunted {
inline void readTextLines(std::istream &stream,std::vector<std::string> &destination){
  std::string line;
  while(std::getline(stream,line)){
    line.erase(std::remove(line.begin(),line.end(),'\r'),line.end());
    destination.push_back(line);
  }
  if(!stream.eof())throw std::runtime_error("Failed while reading text asset");
}
}
