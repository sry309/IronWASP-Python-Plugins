#Author: Lavakumar Kuppan
#License: MIT License - http://www.opensource.org/licenses/mit-license
from IronWASP import *
from System import *
import clr
import re

#Inherit from the base ActivePlugin class
class RemoteFileInclude(ActivePlugin):

  prefixes = ["", "http://", "https://"]
  suffixes = ["", "/", "/a"]
  
  def GetInstance(self):
    p = RemoteFileInclude()
    p.Name = "Remote File Include"
    p.Description = "Active Plugin to check for Remote File Include vulnerabilities"
    p.Version = "0.4"
    return p
  
  #Override the Check method of the base class with custom functionlity
  def Check(self, scnr):
    self.scnr = scnr
    self.confidence = 0
    self.RequestTriggers = []
    self.ResponseTriggers = []
    self.TriggerRequests = []
    self.TriggerResponses = []
    self.TriggerCount = 0
    self.reasons = []
    self.CheckForRemoteFileInclude()
  
  def CheckForRemoteFileInclude(self):
    self.scnr.Trace("<i<br>><i<h>>Checking for Remote File Include:<i</h>>")
    self.CheckForEchoBasedRemoteFileInclude()
    self.CheckForTimeBasedRemoteFileInclude()
    self.AnalyzeTestResult()
    
  def CheckForEchoBasedRemoteFileInclude(self):
    self.scnr.Trace("<i<br>><i<h>>Checking for Remote File Include with Echo:<i</h>>")
    for p in self.prefixes:
      for s in self.suffixes:
        payload = "{0}www.iana.org{1}".format(p, s)
        self.scnr.RequestTrace("  Injected payload - {0}".format(payload))
        res = self.scnr.Inject(payload)
        if res.BodyString.count("IANA is responsible for coordinating the Internet") > 0:
          self.AddToTriggers(payload, "IANA is responsible for coordinating the Internet")
          self.scnr.ResponseTrace("	==> <i<cr>>Response includes content from http://www.iana.org/. Indicates RFI<i</cr>>")
          self.SetConfidence(3)
          reason = self.GetEchoReason(payload, "IANA is responsible for coordinating the Internet", self.TriggerCount)
          reason = "<i<b>><i<cb>>Reason {0}:<i</b>><i</cb>> <i<br>>".format(len(self.reasons) + 1) + reason
          self.reasons.append(reason)
        else:
          self.scnr.ResponseTrace("	==> Response does not seem to contain content from http://www.iana.org/.")
  
  def CheckForTimeBasedRemoteFileInclude(self):
    self.scnr.Trace("<i<br>><i<h>>Checking for Remote File Include with Time Delay:<i</h>>")
    self.IsResponseTimeConsistent = True
    for p in self.prefixes:
      for s in self.suffixes:
        sd = self.GetUniqueSubdomain()
        payload = "{0}<sub_domain>.example.org{1}".format(p, s)
        if self.IsResponseTimeConsistent:
          self.CheckForRemoteFileIncludeWithSubDomainDelay(payload)
        else:
          break
  
  def CheckForRemoteFileIncludeWithSubDomainDelay(self, payload_raw):
    worked = 0
    for ii in range(4):
      res_times = []
      if worked == 2:
        self.SetConfidence(1)
        return
      sub_domain = str(self.GetUniqueSubdomain())
      payload = payload_raw.replace("<sub_domain>", sub_domain)
      first_time = 0
      last_res_time = 0
      for i in range(4):
        if i == 0:
          self.scnr.Trace("<i<br>><i<b>>Sending First Request with Payload - {0}:<i</b>>".format(payload))
        self.scnr.RequestTrace("  Injected payload - {0}".format(payload))
        res = self.scnr.Inject(payload)
        res_times.append(res.RoundTrip)
        if i==0:
          req_current = self.scnr.InjectedRequest
          res_current = res
          first_time = res.RoundTrip
          self.scnr.ResponseTrace("	==> Response time is {0}ms. This will be treated as the base time.".format(res.RoundTrip))
        else:
          if i == 1:
            last_res_time = res.RoundTrip
          else:
            if res.RoundTrip > (last_res_time + 150) or res.RoundTrip < (last_res_time - 150):
              self.IsResponseTimeConsistent = False
              self.scnr.Trace("<i<br>><i<b>>Response times are inconsistent, terminating time based RFI check.<i</b>>")
              return
          if res.RoundTrip >= first_time - 300:
            self.scnr.ResponseTrace("	==> Response time is {0}ms which is not 300ms lower than base time. Not an indication of RFI".format(res.RoundTrip))
            break
          else:
            self.scnr.ResponseTrace("	==> Response time is {0}ms which is 300ms lower than base time. If this is repeated then it could mean RFI".format(res.RoundTrip))
        if i == 3:
          worked = worked + 1
          self.scnr.SetTraceTitle("RFI Time Delay Observed Once", 5)
          if worked == 2:
            self.RequestTriggers.append(payload)
            self.ResponseTriggers.append("")
            self.TriggerRequests.append(req_current)
            self.TriggerResponses.append(res_current)
            self.scnr.Trace("<i<br>><i<cr>>Got a delay in first request with payload - {0}. The three requests after that with the same payload took 300ms less. Infering that this is due to DNS caching on the server-side this is a RFI!<i</cr>>".format(payload))
            reason = self.GetDelayReason(payload, res_times, "{0}.example.org".format(sub_domain), self.TriggerCount + 1)
            reason = "<i<b>><i<cb>>Reason {0}:<i</b>><i</cb>> <i<br>>".format(len(self.reasons) + 1) + reason
            self.reasons.append(reason)
  
  def GetUniqueSubdomain(self):
    sd = "{0}r{1}".format(str(self.scnr.ID), Tools.GetRandomNumber(1, 10000))
    return sd
  
  def SetConfidence(self, conf):
    if conf > self.confidence:
      self.confidence = conf
  
  def AnalyzeTestResult(self):
    if len(self.RequestTriggers) > 0:
      self.ReportRemoteFileInclude()
  
  def AddToTriggers(self, RequestTrigger, ResponseTrigger):
    self.RequestTriggers.append(RequestTrigger)
    self.ResponseTriggers.append(ResponseTrigger)
    self.TriggerRequests.append(self.scnr.InjectedRequest.GetClone())
    self.TriggerResponses.append(self.scnr.InjectionResponse.GetClone())
    self.TriggerCount = self.TriggerCount + 1
  
  def ReportRemoteFileInclude(self):
    pr = Finding(self.scnr.InjectedRequest.BaseUrl)
    pr.Title = "Remote File Include Found"
    #pr.Summary = "Remote File Include been detected in the '{0}' parameter of the {1} section of the request.<i<br>>This was tested by injecting a payload with a unique domain name, then time taken to fetch the response is noted. If subsequent requests with the same payload return quicker then it is inferred that DNS cachcing of the domain name in the payload by the server has sped up the response times.<i<br>><i<br>><i<hh>>Test Trace:<i</hh>>{2}".format(self.scnr.InjectedParameter, self.scnr.InjectedSection, self.scnr.GetTrace())
    pr.Summary = "Remote File Include been detected in the '{0}' parameter of the {1} section of the request.<i<br>><i<br>>{2}<i<br>><i<br>>{3}".format(self.scnr.InjectedParameter, self.scnr.InjectedSection, self.GetSummary(), self.GetTrace())
    for i in range(len(self.RequestTriggers)):
      pr.Triggers.Add(self.RequestTriggers[i], self.TriggerRequests[i], self.ResponseTriggers[i], self.TriggerResponses[i])
    pr.Type = FindingType.Vulnerability
    pr.Severity = FindingSeverity.High
    if self.confidence == 3:
      pr.Confidence = FindingConfidence.High
    elif self.confidence == 2:
      pr.Confidence = FindingConfidence.Medium
    else:
      pr.Confidence = FindingConfidence.Low
    self.scnr.AddFinding(pr)
    self.scnr.SetTraceTitle("Remote File Include",10)

  def GetTrace(self):
    Trace = "<i<hh>>Scan Trace:<i</hh>><i<br>><i<br>>"
    Trace = Trace + "This section contains trace information about the various tests that were performed during this particular scan, the payloads sent during these tests, the application's response to these payloads and the scanner's interpretation of these responses."
    Trace = Trace + "<i<br>>This vulnerability was identified by <i<b>>Scan ID {0}<i</b>>".format(self.scnr.ID)
    
    Trace = Trace + "<i<br>><i<br>>To view the requests and responses associated with this check please head over to the 'Scan Trace' section which is under the 'Automated Scanning' section. "
    Trace = Trace + "<i<br>>There would be a list of scan traces in this section, select the trace entry with the values:<i<br>>    <i<cb>>SCAN ID<i</cb>> - {0}<i<br>>    <i<cb>>CHECK<i</cb>> - {1}<i<br>>    <i<cb>>SECTION<i</cb>> - {2}<i<br>>    <i<cb>>PARAMETER<i</cb>> - {3}".format(self.scnr.ID, self.Name, self.scnr.InjectedSection, self.scnr.InjectedParameter)
    Trace = Trace + "<i<br>><i<br>>Selecting the entry would display the trace overview with the list of payloads sent and the corresponding response code, time etc. After this click on the 'Load this Trace in Viewer' button to view the exact requests and responses associated with this particular check."
    
    Trace = Trace + "<i<br>><i<br>>In the trace information below you would see repeated occurrences of a number followed by the pipe character, <i<b>>eg: 245| Some text here<i</b>>. This number is the log id of the request sent corresponding to that line of scan trace. You can view this request and response from the 'Scan Log' section of the 'Logs' section by using this id as reference. "
    
    Trace = Trace + "<i<br>><i<br>>    <i<b>><< Trace Information Starts From Here >><i</b>><i<br>><i<br>>{0}<i<br>><i<br>>    <i<b>><< Trace Information Ends Here >><i</b>>".format(self.scnr.GetTrace())
    return Trace

  def GetSummary(self):
    Summary = "Remote File Include is an issue where it is possible execute or load contents from a file located on some remote web server through the target application. For more details on this issue refer <i<cb>>http://en.wikipedia.org/wiki/File_inclusion_vulnerability<i</cb>><i<br>><i<br>>"
    Summary = Summary + "IronWASP has reported this issue because of the following reasons:<i<br>><i<br>>"
    for reason in self.reasons:
      Summary = Summary + reason + "<i<br>><i<br>>"
    return Summary
  
  def GetEchoReason(self, payload, echo_content, Trigger):
    payload  = Tools.EncodeForTrace(payload)
    #Reason = "IronWASP sent <i>http://www.iana.org/a</i> as payload to the application. This payload refers to the home page of IANA. ".format(payload)
    Reason = "IronWASP sent <i<hlg>>{0}<i</hlg>> as payload to the application. This payload refers to the home page of IANA. ".format(payload)
    #Reason = Reason + "The response that came back for this payload had the string <i>IANA is responsible for coordinating the Internet</i>. ".format(payload)
    Reason = Reason + "The response that came back for this payload had the string <i<hlg>>{0}<i</hlg>>. ".format(echo_content)
    Reason = Reason + "This string is found in the home page of IANA. This indicates that the application fetched the home page of IANA and returned it in the response, which is RFI."
    
    #Trigger
    Reason = Reason + "<i<br>><i<br>>The request and response associated with this check can be seen by clicking on Trigger {0}.".format(Trigger)
    Reason = Reason + "<i<br>>Doing a right-click on a Trigger id will show a menu with options to resend selected request or to send it after editing. Click on the 'Select this Request for Manual Testing' option in that menu for this feature."
    
    #False Positive Check
    Reason = Reason + "<i<br>><i<br>><i<cg>><i<b>>False Positive Check:<i</b>><i</cg>><i<br>>"
    Reason = Reason + "To check if this was a valid case or a false positive you can first manually look at the response sent for this payload and determine if it actually contains the contents of the IANA website. After that you can try loading contents of other URLs and check if they get added in the response."
    Reason = Reason + "<i<br>>If you discover that this issue was a false positive then please consider reporting this to <i<cb>>lava@ironwasp.org<i</cb>>. Your feedback will help improve the accuracy of the scanner."
    return Reason

  def GetDelayReason(self, payload, res_times, domain, trigger):
    payload  = Tools.EncodeForTrace(payload)
    #Reason = "IronWASP sent <i>http://abcd1234.example.org/a</i> four times to the application. The first time the payload was sent the response came back in 789ms. "
    Reason = "IronWASP sent <i<hlg>>{0}<i</hlg>> four times to the application. The first time the payload was sent the response came back in <i<hlg>>{1}ms<i</hlg>>. ".format(payload, res_times[0])
    #Reason = Reason + "The second, third and fourth time the responses came back in <i<hlg>>204ms<i</hlg>>, <i<hlg>>140ms<i</hlg>> and <i<hlg>>134ms<i</hlg>> respectively. ".format(res_times[1], res_times[2], res_times[3])
    Reason = Reason + "The second, third and fourth time the responses came back in <i<hlg>>{0}ms<i</hlg>>, <i<hlg>>{1}ms<i</hlg>> and <i<hlg>>{2}ms<i</hlg>> respectively. ".format(res_times[1], res_times[2], res_times[3])
    Reason = Reason + "The second, third and fourth responses came back atleast 300ms quicker than the first one. "
    #Reason = Reason + "<i>abcd1234.example.org</i> is an invalid subdomain. "
    Reason = Reason + "<i<hlg>>{0}<i</hlg>> is a non-existent subdomain. If the server had RFI vulnerability then it would try to connect to this non-existent domain. ".format(domain)
    Reason = Reason + "The first time the DNS resolution would have taken extra time. Subsequent attempts to connect to the same domain would be quicker due to DNS caching. Since similar behaviour was observed  for the payload this indicates a RFI vulnerability."

    #Trigger
    Reason = Reason + "<i<br>><i<br>>The request and response associated with this check can be seen by clicking on Trigger {0}".format(trigger)
    Reason = Reason + "<i<br>>Doing a right-click on a Trigger id will show a menu with options to resend selected request or to send it after editing. Click on the 'Select this Request for Manual Testing' option in that menu for this feature."
    
    #False Positive Check
    Reason = Reason + "<i<br>><i<br>><i<cg>><i<b>>False Positive Check:<i</b>><i</cg>><i<br>>"
    Reason = Reason + "To check if this was a valid case or a false positive you can first manually send the same payload but by changing the domain name to some other non-existent domain. "
    Reason = Reason + "Send this modified payload multiple times and check if the first time takes about 300ms longer than the subsequent attempts. "
    Reason = Reason + "If this behaviour is observed repeatedly then this is mostly likely a genuine RFI.<i<br>>"
    Reason = Reason + "Ofcourse the most concrete way to check this is to refer to a page on one of your public web servers in the payload and check if the target sever fetched that page."
    Reason = Reason + "<i<br>>If you discover that this issue was a false positive then please consider reporting this to <i<cb>>lava@ironwasp.org<i</cb>>. Your feedback will help improve the accuracy of the scanner."
    return Reason

p = RemoteFileInclude()
ActivePlugin.Add(p.GetInstance())
