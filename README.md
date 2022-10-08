# System-Manager
*Version: 0.0.1*

System-Manager will update your system and upgrade your applications. You can also install applications as well!

### Usage:
| Short Flag | Long Flag | Description                                      |
| --- | ------|--------------------------------------------------|
| -h | --help         | See usage for script                             | 
| -a | --applications | Applications to installn                         | 
| -f | --file         | File of applications to install                  | 
| -i | --install      | Install applications                             | 
| -s | --silent       | Don't print to stdout                            | 
| -u | --update       | Update your applications and Operating System    | 

### Example:
```bash
system-manager --file apps.txt --update --install --application 'python3'
```


#### Build Instructions
Build Python Package

```bash
sudo chmod +x ./*.py
sudo pip install .
python3 setup.py bdist_wheel --universal
# Test Pypi
twine upload --repository-url https://test.pypi.org/legacy/ dist/* --verbose -u "Username" -p "Password"
# Prod Pypi
twine upload dist/* --verbose -u "Username" -p "Password"
```
