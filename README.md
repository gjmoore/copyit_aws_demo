
# copyit_aws_demo: A step-by-step AWS compute application container deployment example

copyit_aws_demo illustrates an AWS Batch/Fargate targeted workflow for
deploying parallel scientific applications in the cloud.

The following example assumes:

* You have an AWS account

    All demonstration examples in this repository can be run entirely
    within an AWS Free Tier account (https://aws.amazon.com/free)

* The AWS Command-Line Interface (AWS CLI) has been installed on your
  local machine

    See https://aws.amazon.com/cli/

* AWS Python SDK boto3 has been installed (Python 3.9+, installation
  within a virtual environment is recommended)

    ```
    # for example:
    $ python -m venv copyit_demo_aws
    $ . copyit_demo_aws/bin/activate
    $ pip install boto3
    ```

* The following environment variable definitions are useful, and
  assumed:

    ```
    # after installing the AWS CLI:
    $ export AWS_REGION=$(aws configure get region)
    $ export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    ```

## Roadmap:

This demo implements a simple AWS Simple Storage Service (AWS S3)
"copy" operation that essentially mimics functionality already in the
AWS CLI, "`aws s3 cp`". It's deliberately simple so as not to detract
from the primary goal of illustrating the process of building,
deploying, and running containerized compute applications on AWS using
EC2, Batch, and Fargate, while serving as a template for more complex
applications.

The example will follow a workflow that's typical of a general
approach to deploying scientific applications in the cloud:

1. Locally develop and test a Python-based containerized solution.

2. Deploy and test the application in the cloud using AWS Elastic
   Container Registry (AWS ECR) and Elastic Compute Cloud (AWS EC2)
   services.

3. "Serverless" deployment of the container-based application for
   "embarassingly parallel" scalable applications on
   AWS/Batch/Fargate.


## Step 1. Local Python containerized application development and test:

Ref. `Dockerfile.base`, `Dockerfile.run`, `./copyit_pkg`, and
`copyit_run.sh`.

* Build Docker image:

    ```
    $ docker image build -f Dockerfile.base -t copyit_img .
    ```

* Run container locally, interactively, via mounted AWS credentials:

    AWS credentials on your local machine (by default at `(~/.aws)`)
    can be mounted into the container to provide authorization to copy
    AWS S3 object(s) within the cloud:

    ```
    # launch a container, with interactive shell prompt:
    $ docker run --rm -it -v ~/.aws:/root/.aws copyit_img /bin/bash
    ```

    (Note: some trivial data for demo purposes is in `./test/data`, along with an
    upload script at `./test/s3_setup.sh`. The following assumes these data, or
    something similar, have been uploaded to `s3://copyit/source`.)

* Run the copyit application:

    Once the container has been launched and returned a shell prompt,
    the `copyit` application can be run at the container's command
    line:

    ```
    # copyit --src s3://copyit/source/file_a.txt --dest s3://copyit/dest/file_a.txt --log INFO
    INFO:copyit.copyit:copying s3://copyit/source/file_a.txt to s3://copyit/dest/file_a.txt...
    INFO:copyit.copyit:...done
    ```
    
    With the addition of a Dockerfile `ENTRYPOINT`, the container can
    also be run locally as an executable (ref. `Dockerfile.run` and
    `copyit_run.sh`), with AWS S3-based i/o endpoints specified via
    `SRC_OBJECT` and `DEST_OBJECT` environment variables, and local
    AWS credentials as before:

    ```
    $ docker image build -f Dockerfile.run -t copyit_run_img .

    $ docker run \
      -v ~/.aws:/root/.aws \
      -e SRC_OBJECT='s3://copyit/source/file_a.txt' \
      -e DEST_OBJECT='s3://copyit/dest/file_a.txt' \
      copyit_run_img
    ```


## Step 2: Deploy and test application in the cloud using ECR and EC2:

Once the container has been locally validated, migrating to an EC2
virtual machine instance is the next logical step. To do so, an EC2
instance needs to be created, and the container image needs to be made
available on it.  Since logging in and running within an EC2 instance
is much like any other linux session, once could simply `git clone`
this repo and build/run `copyit` from the command line as
before. However, since AWS Batch pulls and runs images from the ECR,
we'll take that approach here, first building and pushing our image to
the ECR from a local machine, and then pulling it into, and running it
from, our EC2 instance. In so doing, we'll gain familiarity with
aspects of the AWS/Batch/Fargate workflow that will be used in
subsequent steps.

To build and push images to the ECR, we'll follow essentially the same
procedure for building Docker images, the only change being that
certain AWS-specific naming conventions need to be adopted that
include the account number and region strings in the image name. One
can begin with using the AWS Console to create an ECR repository into
which we'll upload our container image(s). From the console, go to
ECR, and select "Create" a repository. The only real choice to be made
is that of the repository name, a portion of which is already filled
out according to a standardized naming convention,
`<account>.dkr.ecr.<region>.amazonaws.com/`. The `namespace/repo-name`
portion can be provided as `copyit/copyit_run`.  All of the other
default settings in the console can be used to "create" the
repository. It is into this repository that the `latest` tag of our
Docker image will be pushed.

To build an image on your local machine that will subsequently be
pushed to the ECR:

    ```
    $ docker image build --platform linux/amd64 \
      -t ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/copyit/copyit_run:latest \
      -f ./Dockerfile_run .
    ```

Note the account and region data in the image name, and the use of the
`--platform` argument which is only required in the case of
cross-platform builds (for example, building an amd64-based image on
Apple silicon (e.g., M-based chips).  Although the `--platform`
argument ensures that the image built on Apple silicon will run on an
amd64-based AWS Free Tier account AMI, note that it wouldn't have been
necessary were an ARM-based AWS AMI (outside of the Free Tier) to have
been selected (i.e., AWS Graviton processors).

To push the image to the ECR repository we just created:

    ```
    $ aws ecr get-login-password | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
    $ docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/copyit/copyit_run:latest
    ```

You can verify a successful image upload by navigating to the ECR in
the AWS Console and clicking on "copyit/copyit_run" under "Private
repositories" and noting the presence of an image tagged as "latest".

Now that we have an image in the ECR that can be pulled into an EC2
instance, we'll set one up next.  Since EC2 instances run within an
AWS virtual private cloud (AWS VPC), one must first be configured to
host the instance. Indeed, since AWS Batch will spin up EC2 instances
within a defined compute environment's VPC in response to job
submittal requests, the process of defining a VPC not only facilitates
the current task, but anticipates the next steps as well.

An AWS Free Tier account comes with a default VPC already configured
that is suitable for this task, or you can create another one yourself
(if you had, for example, subnet or routing table preferences), and a
Free Tier-level EC2 instance (e.g., t3.micro) is more than adequate to
host the `copyit` application. The following steps can all be
performed from the AWS Console:

* Create VPC, or use the Free Tier account's default VPC:

    Either way, the VPC should include:

    - Subnet(s) that route to an internet gateway (ref. VPC ->
    Resource map in the AWS Console; a VPC that connects to the
    internet will have an "igw"-type network connection shown in the
    graphical resource map)

    - Auto-assign public IPv4 addresses set to "yes" (allows EC2
    instances created in the VPC's subnet(s) to connect via the VPC's
    internet gateway; to verify, from the Resource map of the VPC
    you'll be using to host the EC2 instance, select the subnet(s) and
    verify in the breakout window that "Auto-assign public IPv4
    address" under "Details" is "Yes")

* Create, launch, and configure an EC2 instance in the VPC:

    - Can generally follow steps in the AWS EC2 console for instance
    creation, making sure to select a Free Tier-available Amazon
    Machine Image (AMI) and Instance Type (e.g., t3.micro, t3.small,
    etc.), selecting the VPC defined above, and using the default
    security group.

    - Regarding the choice of "Key pair (login)", though the AWS
    Console will note that proceeding without a key pair is "not
    recommended", it's generally less troublesome to not use a key
    pair since doing so will tie your EC2 instance to a single user,
    from a single host, and it can't be changed externally after
    launching the instance. Although proceeding without a key pair
    means you won't be able to connect to the host via SSH you will,
    however, be able to connect via the AWS Console's Systems Manager
    Session Manager which is quite straightforward, and will also
    allow you, or anyone else in your account group, to connect to the
    instance from a browser window on any host.

     - Launch the EC2 instance from the AWS Console and, after it
     boots and runs through the system checks (usually only a couple
     of minutes), select the instance and "Connect" via the Session
     Manager, which will launch a `bash` shell in the console browser
     window.

     - Configure the instance, e.g.:

        ```
        $ cd ~
        $ sudo dnf update
        $ sudo install -y docker

        # note that docker runs as root:
        $ sudo systemctl enable --now docker
        # make sure docker is running:
        $ sudo docker image ls

        # also, for convenience, define AWS_REGION and AWS_ACCOUNT_ID locally, or add to .bash_profile and source, e.g.:
        $ cd ~
        $ echo "export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)" >> .bash_profile
        $ echo "export AWS_REGION=$(ec2-metadata -R | awk '{print $2}')" >> .bash_profile
        $ . ./.bash_profile
        ```

    - Pull the Docker image from the ECR and verify that it's
      available on our EC2 instance:

        ```
        # note "sudo docker" here too as well
        $ aws ecr get-login-password | \
        sudo docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

        $ sudo docker pull ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/copyit/copyit_run

        $ sudo docker image ls
        REPOSITORY                                                              TAG       IMAGE ID       CREATED          SIZE
        <aws_account_id>.dkr.ecr.<aws_region>.amazonaws.com/copyit/copyit_run   latest    4d4cef3a27df   47 minutes ago   369MB
        ```

    - Run the containerized application in the EC2 instance:

        In much the same way as before:

        ```
        $ sudo docker run \
            -e SRC_OBJECT='s3://copyit/source/file_a.txt' \
            -e DEST_OBJECT='s3://copyit/dest/file_a.txt' \
            <aws_account_id>.dkr.ecr.<aws_region>.amazonaws.com/copyit/copyit_run
        ```

        In the above note that, in addition to using the Docker image
        pulled from the ECR, we didn't have to volume mount
        credentials, as the EC2 instance has been launched from our
        account, with an IAM role (that we defined), that includes s3
        access.

        `^D` or "Terminate" to log out of the instance and, if you wish, "Stop"
        the instance via the "Instance State" pulldown from the "Instance
        summary" page (not generally a concern for Free Tier instances, but
        larger instances will incur running costs).


## Step 3: AWS Batch/Fargate "serverless" deployment:

At the risk of wading into marketing-related jargon, generally
speaking, AWS Batch is a managed service that provides job definition,
scheduling, and resource management for container workloads that can
leverage, among others, AWS Fargate for container-centric "serverless"
compute provisioning.

That's rather saying a lot.

In the context of this example demo, AWS Batch can be thought of as
providing the job definition and job queueing/scheduling framework,
while AWS Fargate can be thought of as the compute resource
provider. In fact, using AWS Fargate is arguably the easiest way to
get started with Batch.

As in the case of EC2 testing and deployment, all of the setup for
Batch/Fargate can be accomplished via the AWS Console. In a big
picture sense, we'll define the compute environment, set up a job
definition and queue, and submit jobs. Though job submittal can be
done from the console we'll use the CLI in order to demonstrate how to
run "embarassingly parallel" jobs at scale.

* Define an AWS Batch Compute Environment:

    From the AWS Batch Console, select "Environments", "Create
    Environment", and select the dropdown choice, "Compute
    Environment". Note that the Fargate configuration is automatically
    selected (lower-cost Fargate "spot" instances are fine for this
    example). The compute environment needs to be given a name (for
    example, "copyit-compute-env"). Note that a service role
    (AWSServiceRoleForBatch) has already been defined.  On the next
    page, the maximum number of cpus can be set to a small number
    (i.e., 2, 4, etc.), which controls the maximum number of EC2 vcpus
    that Batch/Fargate will provision at any one time. On the next
    page, the VPC and subnet(s) created and/or used in the EC2
    instance demo can be used, and the default security group is,
    again, fine.

* Define a job queue:

    The job queue is the entity used by the Batch scheduler to route
    jobs to the compute environment just defined, and also defines
    priority and job state limits. From the AWS Console, select "Job
    queues", "Create", note that Fargate is the pre-selected
    Orchestration type, give the queue a name (e.g.,
    "copyit-job-queue"), and connect it to the compute environment
    just created, "copyit-compute-env". The other defaults should be
    fine.

* Create a job definition:

    The job definition provides a template for resources, e.g., vCPUs,
    memory, container image, etc. Again, from the AWS Batch console
    select "Create", note that the Fargate orchestration type has been
    pre-selected, give the job definition a name (e.g.,
    "copyit-job-definition", select an execution IAM role (*), under
    "Container configuration", "Image", enter the image we previously
    pushed to AWS ECR, e.g.,
    `<aws_account_id>.dkr.ecr.<aws_region>.amazonaws.com/copyit/copyit_run:latest`,
    and delete the optional "Command" (this will be provided by the
    Docker container `ENTRYPOINT` previously defined). Also, under
    "Environment configuration", "Job role configuration", for
    simplicity, you can just reuse the IAM execution role used
    previously (in this case, in order to allow our running containers
    to access AWS S3 object storage).

    (*) Not much has purposely been said so far about AWS Identity and
    Access Management (IAM), mostly because it's a wide-ranging topic,
    affecting virtually all AWS operations. In short, IAM is the
    scheme whereby a "Principal" (either an actual user or a service
    acting on the user's behalf, for example, the AWS Elastic
    Container Service in an AWS Batch context), is given the
    authorization to do specific things such as access objects on
    S3. IAM is the "are you who you say you are and what are you
    allowed to do" context behind every service request. In the
    context of this demo, a Batch execution role is referenced when
    creating a job definition (see "Create Execution Role"). Selecting
    it will open an IAM->Roles->Create role dialogue from which you
    can (assuming you have administrative privileges which, in the
    case of a Free Tier account, you do) accept all defaults on the
    first page (AWS Service Trusted Entity Type and Elastic Container
    Service Use case), and then add "AmazonS3FullAccess" on the second
    "Add permissions" page. On the third page you can give it a name
    (e.g., "copyit-batch-execution-role") or just leave the default
    "BatchEcsTaskExecutionRole", and wrap up by selecting the "Create
    role" button.

* Run AWS Batch job(s):

    With a compute environment, queue, and job definition all defined,
    we can finally submit batch jobs. Although one could do so via
    "Jobs"->"Submit new job" in the AWS Batch console, that's a rather
    tedious process if our compute task consists of multiple jobs, and
    it's ultimately a little more instructive to demonstrate job
    submittal via the AWS CLI, which easily allows multiple jobs (tens
    or hundreds) to be submitted and provisioned at once.

    Recall that our container used two environment variables,
    `SRC_OBJECT` and `DEST_OBJECT` to specify the source object to be
    copied and the name of the copy, respectively. The included
    `copyit_run_aws_batch.sh` is a script that can be run on either
    your local machine (pretty neat, huh?!) or an EC2 instance that
    sets these environment variables for every source file located in
    `s3://copyit/source/`, and calls the CLI command "`aws batch
    submit-job`" to copy each to their respective `DEST_OBJECT`
    locations. Note that the "`--job-definition`" argument is the
    "hook" that references the container image to be run.

    All that's required to harness the power of AWS Batch and Fargate
    then, is to run the shell script:

    ```
    $ ./copyit_run_aws_batch.sh
    ```
        
    You can monitor job progress via the console at AWS Batch ->
    "Jobs". Once the status of a job or jobs is "Succeeded", clicking
    on the job name will route to a page of job details, one of which
    is a "Log stream name" link to the AWS CloudWatch Log events, that
    is, our Python application logging messages. And, of course, the
    S3 console can be used to verify the results of the copy
    operation.

    So that's it; pretty neat, huh?! Good luck!

