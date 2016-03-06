Vagrant.configure(2) do |config|
	config.vm.box = "bandienkhamgalan/seldonucldcs"
	config.vm.box_version = ">=0.5"
	config.vm.network :forwarded_port, host: 5000, guest: 80, auto_correct: true
	config.vm.provision :shell, path: "vagrant_provisioning/bootstrap.sh"
	config.vm.provision :shell, path: "vagrant_provisioning/startup.sh", run: "always"
end