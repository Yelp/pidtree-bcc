.PHONY: run-nodocker

ROOTFS?=opt/pidtree-bcc-rootfs

pidtree-bcc.tar:
	docker export -o $@ pidtree-bcc

$(ROOTFS): pidtree-bcc.tar
	mkdir $@
	tar xf $< --ignore-command-error -C $@/ --exclude='dev/*'

run-nodocker: $(ROOTFS)
	sudo unshare --net --mount --propagation slave --uts --ipc --fork ./enter-ns.sh
