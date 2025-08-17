FROM jenkins/jenkins:2.504.3-lts-jdk17

USER root

# skip the setup wizard, we have JCasC
ENV JAVA_OPTS=-Djenkins.install.runSetupWizard=false
# without this the casc.yaml never gets loaded and the wizard pops back up
ENV CASC_JENKINS_CONFIG=/var/jenkins_home/casc.yaml

COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

COPY casc.yaml /var/jenkins_home/casc.yaml
COPY jobs/ /var/jenkins_home/jobs.d/

USER jenkins
