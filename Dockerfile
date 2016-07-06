FROM ubuntu:14.04

MAINTAINER Ilia Yakubovsky

# Update the sources list
RUN apt-get update && apt-get install -y software-properties-common
RUN add-apt-repository ppa:libreoffice/libreoffice-5-1 && apt-get update

# Install basic applications
RUN apt-get install -y tar git curl nano wget dialog net-tools build-essential autoconf python-dev
RUN apt-get install -y pkg-config automake gcc g++ libtool make nasm tar bzip2 libmp3lame-dev 
RUN apt-get install -y libreoffice libjpeg-dev libpng-dev zlib1g-dev

RUN export MAKEFLAGS="-j$[$(nproc) + 1]"

RUN git clone https://github.com/yasm/yasm.git && cd yasm && ./autogen.sh && ./configure &&\ 
  make && make install && make distclean

RUN git clone https://github.com/mstorsjo/fdk-aac.git && cd fdk-aac && autoreconf -fiv &&\
  ./configure --disable-shared && make && make install && make distclean

RUN git clone https://git.xiph.org/speex.git && cd speex && ./autogen.sh &&\
  ./configure --disable-shared && make && make install && make distclean

RUN git clone git://git.videolan.org/x264.git && cd x264 && ./configure --enable-static &&\
  make && make install && make distclean

RUN git clone git://source.ffmpeg.org/ffmpeg.git && cd ffmpeg &&\
  ./configure --extra-libs=-ldl --enable-gpl --enable-libfdk-aac --enable-libmp3lame\
  --enable-libx264 --enable-libspeex --enable-nonfree && make && make install && make distclean

RUN git clone git://git.ghostscript.com/ghostpdl.git && cd ghostpdl && ./autogen.sh &&\
  ./configure && make && make install && make distclean

RUN wget https://bootstrap.pypa.io/ez_setup.py -O - | python

ADD . /tbrecordings
WORKDIR /tbrecordings
RUN python setup.py install

RUN useradd -m deplo
USER deplo

ENV HOME /home/deplo/
ENV AWS_CONFIG_FILE $HOME.aws/config

RUN mkdir $HOME/.aws/

COPY config $AWS_CONFIG_FILE

ENTRYPOINT tbrecording -i $INPUT