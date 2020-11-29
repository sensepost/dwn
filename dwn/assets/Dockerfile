FROM alpine

# This dockerfile is used for network forwarding to services.

ENV REMOTE_HOST=localhost
ENV REMOTE_PORT=80
ENV LOCAL_PORT=80

RUN apk add --update --no-cache \
		socat \
	&& rm -rf /var/cache/apk/

CMD socat -d -d tcp-listen:$LOCAL_PORT,reuseaddr,fork tcp:$REMOTE_HOST:$REMOTE_PORT & pid=$! && \
    trap "kill $pid" SIGINT && \
    trap "kill $pid" SIGTERM && \
	echo "forwarding $LOCAL_PORT to $REMOTE_HOST:$REMOTE_PORT ($pid)" && \
	wait $pid
