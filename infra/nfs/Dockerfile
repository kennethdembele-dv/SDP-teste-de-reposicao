# Servidor NFSv4 em espaco de utilizador (NFS-Ganesha): nao depende do modulo nfsd do kernel.
FROM debian:bookworm-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends nfs-ganesha nfs-ganesha-vfs \
 && rm -rf /var/lib/apt/lists/*
COPY ganesha.conf /etc/ganesha/ganesha.conf
RUN mkdir -p /exports/dfs/imagens /exports/dfs/relatorios /run/ganesha && chmod -R 777 /exports/dfs
EXPOSE 2049
CMD ["ganesha.nfsd", "-F", "-L", "/dev/stdout", "-f", "/etc/ganesha/ganesha.conf"]
