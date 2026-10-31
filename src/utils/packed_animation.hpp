#pragma once
#include "../base/read_lines.hpp"
#include <cmath>
#include <array>
#include <cstring>
#include <cstdint>
#include <iomanip>
#include <limits>
#include <locale>
#include <sstream>

namespace blunted {
// Float-exact packed tracks. ZIP compresses this binary representation much
// better than decimal text; poses and contact metadata are not quantized.
inline bool readPackedAnimation(std::istream &stream,std::vector<std::string> &lines){
  char magic[5]{};stream.read(magic,5);
  const bool predictive=std::memcmp(magic,"FBAN2",5)==0;
  if(!predictive&&std::memcmp(magic,"FBAN1",5)!=0)return false;
  auto byte=[&](){const int b=stream.get();if(b==std::char_traits<char>::eof())throw std::runtime_error("Truncated packed animation");return unsigned(b);};
  auto integer=[&](){std::uint32_t n=0;for(unsigned i=0;i<4;++i)n|=byte()<<(8*i);return n;};
  const auto count=integer();if(count!=14)throw std::runtime_error("Invalid packed animation track count");
  for(unsigned track=0;track<count;++track){
    const unsigned length=byte();if(length==0||length>64)throw std::runtime_error("Invalid packed track name");
    std::string name;for(unsigned i=0;i<length;++i)name+=char(byte());
    const unsigned width=byte(),size=integer();
    if(width!=(name=="player"?3u:4u)||size==0||size>20000)throw std::runtime_error("Invalid packed pose dimensions");
    std::vector<std::uint32_t> times(size);
    std::vector<std::array<float,4>> values(size);
    if(predictive){
      for(auto &time:times)time=integer();
      for(unsigned axis=0;axis<width;++axis){
        std::vector<std::uint32_t> residuals(size,0);
        for(unsigned plane=0;plane<4;++plane)for(auto &value:residuals)value|=byte()<<(plane*8);
        std::uint32_t previous1=0,previous2=0;
        for(unsigned k=0;k<size;++k){
          const auto encoded=residuals[k];
          const std::uint32_t residual=(encoded>>1)^(0u-(encoded&1u));
          const std::uint32_t bits=2u*previous1-previous2+residual;
          std::memcpy(&values[k][axis],&bits,4);previous2=previous1;previous1=bits;
        }
      }
    }else for(unsigned k=0;k<size;++k){
      times[k]=integer();
      for(unsigned axis=0;axis<width;++axis){const auto bits=integer();std::memcpy(&values[k][axis],&bits,4);}
    }
    std::ostringstream row;row.imbue(std::locale::classic());row<<name<<std::setprecision(std::numeric_limits<float>::max_digits10);
    int previous=-1;
    for(unsigned k=0;k<size;++k){
      const auto time=times[k];
      if(time>20000||int(time)<=previous)throw std::runtime_error("Invalid packed pose time");
      previous=int(time);row<<','<<time;
      for(unsigned axis=0;axis<width;++axis){
        const float value=values[k][axis];
        if(!std::isfinite(value))throw std::runtime_error("Nonfinite packed pose value");
        row<<','<<value;
      }
    }
    lines.push_back(row.str());
  }
  const auto size=integer();if(size>1048576)throw std::runtime_error("Packed metadata exceeds its limit");
  std::string footer(size,'\0');stream.read(&footer[0],size);
  if(stream.gcount()!=size||stream.peek()!=std::char_traits<char>::eof())throw std::runtime_error("Invalid packed metadata length");
  std::istringstream metadata(footer);readTextLines(metadata,lines);
  return true;
}
}
