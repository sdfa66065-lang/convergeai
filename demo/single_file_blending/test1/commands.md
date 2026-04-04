### goose_convergeai_chat_history.json

```bash
./converge.sh "There is a merge conflict in test_conflict.py. Call distill_context for commit f0e36e90891e3f15c89809dfc71d745e5bd554e3 to get the rules, then rewrite test_conflict.py to resolve the conflict according to those rules. Do not leave any conflict markers."
```

### goose_native_chat_history.json

```bash
goose run --text "There is a merge conflict in test_conflict.py. Please resolve it without converge ai."
```


### todo: run with profile
```bash
cat << EOF | goose run -i -  
There is a merge conflict in test_conflict.py. The cherrypick commit is commit f0e36e90891e3f15c89809dfc71d745e5bd554e3 of repository sdfa66065-lang/convergeai. Please address it with the instructions from /Users/sabrinayu/Documents/GitHub/convergeai/goose/ai-maintainer.yaml

EOF
```

todo: improve the yaml file by adding steps of reading the local merge conflicts, get github repository + cherrypick commit and/or pull request and/or jira ticket

```bash
goose run --instructions /Users/sabrinayu/Documents/GitHub/convergeai/goose/ai-maintainer.yaml
```