# `emphprod`: EMPHATIC collaboration production tools
Tools used for EMPHATIC Production

## Documentation

For documentation on the use and maintenance of the tools in this repository, please visit the [Production wiki](https://github.com/EMPHATICSoft/emphprod/wiki)

## Contributing

#### Get a copy of the code
... by [cloning the repository](https://docs.github.com/en/github/creating-cloning-and-archiving-repositories/cloning-a-repository-from-github/cloning-a-repository).

If you have your ssh key setup, this should be as simple as running
```
git clone git@github.com:EMPHATICSoft/emphprod.git
```

#### Contribute to the repository
[Submit a pull request](https://docs.github.com/en/github/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request) on GitHub. 

##### **Create a topic branch**
*(Please note that this will only work if you have write access to the GitHub repository.  All members of the `EMPHATICSoft` team *should* have write access, so this shouldn't be an issue)*

Check out a new branch in your working copy of the repository (the result of cloning it; see "Get a copy of the code" above):
```
git checkout -b feature/${USER}_branch_description
```
Commit your changes onto this branch.

Once you're satisfied, push it to the repository:
```
git push --set-upstream origin feature/${USER}_branch_description
```

(For subsequent pushes to the origin repository from this branch, you can simply `git push`.)

Then, enter the GitHub interface and follow the "Submit a pull request" documentation above.  Please enter meaningful descriptions of your changes so that it's easier to understand them :)

#### Add params to submit 

For future refence on how to add new params (such as memory, disk, particle type, etc) for the submission (example using gen, reco is the same): 
```
emphprod/emphgridutils/bin/submit_emph_art.py gen \
  emphprod/emphgridutils/bin/generateMCJob.sh \
  --njobs 100 \
  --run-number 2408 \
  --first-subrun 1 \
  --nEvts 1000 \
  --memory 4GB \
  --disk 3GB \
```
The new parameters need to be added to emphgridutils/bin/submit_emph_art.py as
```
gen_job.add_argument(
    "--memory",
    type=str,
    default="3GB",
    help="Memory request to grid node worker",
    )
```
if it's a core params (something the grid node needs to know about) change also build_generator_jobsub_command in submit_emph_art_core.py
```
def basic_jobsub_args(
    host_out_dir: Path,
    payload_tarball: Path,
    test_events: int | None = None,
    site: str = "onsite",
    memory: str = "3GB",
    disk: str = "3GB"

 args = [
        "-G",
        "emphatic",
        "-d",
        OUT_DIR_TAG,
        str(host_out_dir),
        "-l",
        "+SingularityImage=\"/cvmfs/singularity.opensciencegrid.org/fermilab/fnal-wn-sl7:latest\"",
        "--tar_file_name",
        f"dropbox://{payload_tarball}",
        "--use-cvmfs-dropbox",
        f"--memory={memory}",
        f"--disk={disk}"
    ]
```

if it's a parameter needed on the fcl:

1. Change the parameter value to something like @@NAMEPARAM@@ in the template fcl
  
2. Add it to emphgridutils/bin/generateMCJob.sh
```
particle=${5:"proton"}
.
.
.
sed "s/@@PARTICLE@@/$particle/g" < withRunSubrunNevts.fcl > withRunSubrunNevtsP.fcl
```
This line will change all instances of @@PARTICLE@@ with the str/values carried by $particle


# Copyright & Licensing
Copyright © 2023 FERMI NATIONAL ACCELERATOR LABORATORY for the benefit
of the EMPHATIC Collaboration.

This repository, and all software contained within, is licensed under
the Apache License, Version 2.0 (the "License"); you may not use this
file except in compliance with the License. You may obtain a copy of
the License at

http://www.apache.org/licenses/LICENSE-2.0

Copyright is granted to FERMI NATIONAL ACCELERATOR LABORATORY on behalf
of the Experiment to Measure the Production of Hadrons At a Test beam 
In Chicagoland (EMPHATIC) experiment. Unless required by
applicable law or agreed to in writing, software distributed under the
License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for
the specific language governing permissions and limitations under the
License.

